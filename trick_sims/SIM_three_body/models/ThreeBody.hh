/************************** TRICK HEADER *************************
PURPOSE:
    (Newtonian three-body dynamics with no fixed central body.)
*****************************************************************/
#ifndef THREE_BODY_HH
#define THREE_BODY_HH

class ThreeBody
{
    public:
        double gravitational_constant; /**< (m3/kg/s2) Newtonian gravitational constant. */
        double mass[3];                /**< (kg) Positive, constant body masses. */
        double position[3][3];         /**< (m) Inertial Cartesian positions. */
        double velocity[3][3];         /**< (m/s) Inertial Cartesian velocities. */
        double acceleration[3][3];     /**< (m/s2) Acceleration from both other bodies. */
        double minimum_distance;       /**< (m) Stop at or below this pair separation. */

        double kinetic_energy;      /**< (J) Total kinetic energy. */
        double potential_energy;    /**< (J) Unsoftened gravitational potential energy. */
        double total_energy;        /**< (J) Kinetic plus potential energy. */
        double momentum[3];         /**< (kg*m/s) Total linear momentum. */
        double angular_momentum[3]; /**< (kg*m2/s) Angular momentum about the origin. */
        double center_of_mass[3];   /**< (m) Mass-weighted position. */
        double closest_distance;    /**< (m) Smallest current pair separation. */

        int default_data();
        int initialize();
        int derivative();
        int integrate_state();
        int diagnostics();
};

#endif
