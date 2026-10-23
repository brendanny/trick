import java.net.DatagramPacket;
import java.net.InetAddress;
import java.net.MulticastSocket;
import trick.common.utils.VariableServerConnection;
import trick.sniffer.SimulationInformation;

/** Runs the command sequences of the Java apps against a SIM and checks the replies. */
public class VsJavaCheck {
    static int failures = 0;

    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }

    public static void main(String[] args) throws Exception {
        String host = args[0];
        int port = Integer.parseInt(args[1]);

        // Sim control panel: the command connection.
        VariableServerConnection cmd = new VariableServerConnection(host, port);
        cmd.put("trick.var_exists(\"trick_master_slave.master.num_slaves\")");
        String[] r = cmd.get().split("\t");
        check(r[0].equals("1") && (r[1].equals("0") || r[1].equals("1")), "simcontrol var_exists: " + String.join("|", r));
        cmd.put("trick.var_set_client_tag(\"SimControl\")\n");
        cmd.put("trick.var_add(\"trick_sys.sched.sim_start\") \n"
                + "trick.var_add(\"trick_sys.sched.terminate_time\") \n"
                + "trick.var_add(\"trick_sys.sched.time_tic_value\") \n"
                + "trick.var_add(\"trick_cmd_args.cmd_args.default_dir\") \n"
                + "trick.var_add(\"trick_cmd_args.cmd_args.cmdline_name\") \n"
                + "trick.var_add(\"trick_cmd_args.cmd_args.input_file\") \n"
                + "trick.var_add(\"trick_cmd_args.cmd_args.run_dir\") \n");
        cmd.put("trick.var_send() \n" + "trick.var_clear() \n");
        r = cmd.get().split("\t");
        boolean parsed = false;
        try {
            double tic = Double.parseDouble(r[3]);
            double start = Double.parseDouble(r[1]);
            long term = Long.parseLong(r[2]);
            parsed = r[0].equals("0") && tic > 0 && start >= 0 && term > 0 && r[6].endsWith("input.py");
        } catch (RuntimeException e) {
            System.out.println("  " + e);
        }
        check(parsed, "simcontrol startup values: " + String.join("|", r));
        cmd.put("trick.var_exists(\"trick_real_time.rt_sync.total_overrun\")\n");
        check(cmd.get().equals("1\t1"), "simcontrol var_exists total_overrun");
        cmd.put("trick.var_exists(\"trick_message.mdevice.port\")\n");
        check(cmd.get().equals("1\t1"), "simcontrol var_exists mdevice.port");
        cmd.put("trick.var_add(\"trick_message.mdevice.port\") \n" + "trick.var_send() \n" + "trick.var_clear() \n");
        r = cmd.get().split("\t");
        check(r[0].equals("0") && Integer.parseInt(r[1]) >= 0, "simcontrol mdevice.port: " + String.join("|", r));

        // Sim control panel: the status connection, streaming at 0.25 s.
        VariableServerConnection status = new VariableServerConnection(host, port);
        status.put("trick.var_set_client_tag(\"SimControl2\")\n");
        status.put("trick.var_add(\"trick_sys.sched.time_tics\") \n"
                + "trick.var_add(\"trick_sys.sched.mode\") \n"
                + "trick.var_add(\"trick_real_time.rt_sync.actual_run_ratio\") \n"
                + "trick.var_add(\"trick_real_time.rt_sync.active\") \n"
                + "trick.var_add(\"trick_real_time.rt_sync.total_overrun\")\n");
        status.put("trick.var_cycle(0.25)\n");
        long t0 = System.nanoTime();
        String line = null;
        for (int i = 0; i < 4; i++) line = status.get();
        double seconds = (System.nanoTime() - t0) / 1e9;
        r = line.split("\t");
        check(r.length == 6 && r[0].equals("0"), "simcontrol status line: " + line);
        check(seconds > 0.5 && seconds < 2.5, "4 status lines at 0.25 s took " + seconds + " s");

        // Actions: run, then freeze (Python fallback lines). The mode is 1 freeze, 5 run.
        cmd.put("trick.exec_run()\n");
        boolean ran = false;
        for (int i = 0; i < 20 && !ran; i++) ran = status.get().split("\t")[2].equals("5");
        check(ran, "exec_run: status shows run mode");
        cmd.put("trick.exec_freeze()\n");
        boolean froze = false;
        for (int i = 0; i < 20 && !froze; i++) froze = status.get().split("\t")[2].equals("1");
        check(froze, "exec_freeze: status shows freeze mode");
        status.close();

        // Trick View: binary, several variables, var_units, validate addresses.
        VariableServerConnection tv = new VariableServerConnection(host, port);
        tv.setClientTag("TRICK_TV");
        tv.pause();
        tv.setValidateAddresses(true);
        tv.setBinary();
        tv.add("conf.vars.i32");
        tv.add("conf.vars.d");
        tv.add("conf.vars.pos", "km");
        tv.add("conf.vars.no_such_var");
        tv.poll();
        String values = tv.get(4);
        // BAD_REF is type 25 in binary, as the old server sent (decision 1). get() knows only 24, so
        // it prints "Unknown type 25" and leaves the value empty, as with the old server.
        check(values.equals("-123456789\t3.141592653589793\t1000.0\t"), "TV binary get(4): " + values);
        tv.clear();
        tv.setAscii();
        tv.add("conf.vars.pos", "km");
        tv.put("trick.var_units(\"conf.vars.pos\", \"cm\")");
        tv.poll();
        values = tv.get();
        check(values.equals("0\t100000 {cm}"), "TV ascii units: " + values);
        tv.clear();
        tv.setBinaryNoNames();
        tv.add("conf.vars.ll");
        tv.poll();
        values = tv.get(1);
        check(values.equals("-9.0E18"), "TV binary nonames long long: " + values);
        tv.setAscii();
        tv.clear();
        tv.put("trick.var_get_stl_size(\"conf.vars.vec\")");
        values = tv.get();
        check(values.equals("6\t3"), "TV var_get_stl_size: " + values);
        tv.close();

        // MTV: binary nonames, semicolon commands on one line, mtv_send_event_data.
        VariableServerConnection mtv = new VariableServerConnection(host, port);
        mtv.pause();
        mtv.put("trick.var_set_client_tag(\"TRICK_MTV\")");
        mtv.setBinaryNoNames();
        mtv.put("trick.var_cycle(0.01)");
        mtv.put("trick.var_add(\"trick_ip.mtv.mtv_count\"); trick.var_send(); trick.var_clear();");
        String count = mtv.get();
        check(count.equals("0"), "MTV mtv_count: " + count);
        mtv.put("trick.mtv_send_event_data();");
        String numvars = mtv.get();
        check(numvars.equals("0"), "MTV send_event_data list size: " + numvars);
        mtv.close();

        // Monte Monitor: tag and a simple Python line.
        VariableServerConnection monte = new VariableServerConnection(host, port);
        monte.setClientTag("TRICK_Monte");
        monte.put("trick.var_set_send_stdio(True)\nimport sys\nsys.stdout.write(\"monte\")");
        char[] buf = new char[64];
        int n = monte.read(buf, 0, buf.length);
        String stdio = new String(buf, 0, Math.max(n, 0));
        check(stdio.equals("4 1 5\nmonte"), "stdio message: " + stdio.replace("\n", "\\n"));
        monte.close();

        // Sniffer: the beacon on 239.3.14.15:9265.
        MulticastSocket ms = new MulticastSocket(9265);
        ms.joinGroup(InetAddress.getByName("239.3.14.15"));
        ms.setSoTimeout(5000);
        byte[] b = new byte[4096];
        boolean found = false;
        long end = System.currentTimeMillis() + 10000;
        while (!found && System.currentTimeMillis() < end) {
            DatagramPacket p = new DatagramPacket(b, b.length);
            try {
                ms.receive(p);
            } catch (java.net.SocketTimeoutException e) {
                continue;
            }
            String[] info = new String(p.getData(), p.getOffset(), p.getLength()).replace("\n", "").split("\t");
            if (info.length >= 12 && info[1].equals(Integer.toString(port))) {
                SimulationInformation si = new SimulationInformation(info[0], info[1], info[2], info[3], info[4],
                        info[5], info[6], info[7], info[8], info[9], info[10], info[11]);
                System.out.println("  beacon: " + String.join("|", info));
                found = info[10].equals("1") && si.getMajorVersionNumber() >= 0;
            }
        }
        ms.close();
        check(found, "sniffer: beacon with 12 fields, enabled=1, for this port");

        cmd.close();
        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILURES");
        System.exit(failures == 0 ? 0 : 1);
    }
}
