"""Reject missing, extra, or reclassified MemoryManager runtime failures."""

import unittest

import baseline as b
import memorymanager as m


def expected_logs(binary="/tmp/S_main_test.exe"):
    return "\n".join(
        f'MemoryManager:ERROR:Couldn\'t find function "io_src_allocate_{name}()". '
        f"dlerror= {binary}: undefined symbol: io_src_allocate_{name}\n"
        f"MemoryManager:ERROR:io_src_allocate_class ({name},1) failed to allocate any memory.\n"
        for name in ("IcgLifecycleNoDefault", "IcgLifecycleAbstract")
    )


class MemoryManagerLogsTests(unittest.TestCase):
    def test_exact_failures_ignore_only_loader_binary_path(self):
        for binary in ("/tmp/S_main.exe", "/a directory/with spaces/S_main.exe"):
            with self.subTest(binary=binary):
                m.validate_logs(expected_logs(binary))

    def test_absent_extra_or_other_failures_are_rejected(self):
        logs = expected_logs()
        for changed in (
            "",
            logs + logs,
            logs.replace("IcgLifecycleAbstract", "IcgLifecycleDeleted"),
            logs.replace("undefined symbol", "unexpected loader failure"),
            logs.replace("(IcgLifecycleAbstract,1)", "(IcgLifecycleAbstract,3)"),
            logs + "\nMemoryManager:WARNING:unexpected warning",
            logs + "\nCheckpoint Agent ERROR: failed",
        ):
            with self.subTest(changed=changed), self.assertRaises(b.BaselineError):
                m.validate_logs(changed)


if __name__ == "__main__":
    unittest.main()
