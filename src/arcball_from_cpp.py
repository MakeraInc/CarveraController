#acrball camera from cpp

import math

def arcball_camera_look_to(
    eye,
    look,
    up,
    flags):
        
    look_len = math.sqrt(look[0] * look[0] + look[1] * look[1] + look[2] * look[2]);
    up_len = math.sqrt(up[0] * up[0] + up[1] * up[1] + up[2] * up[2]);



    # up'' = normalize(up)
    up_norm = [ up[0] / up_len, up[1] / up_len, up[2] / up_len ]

    # f = normalize(look)
    f =[ look[0] / look_len, look[1] / look_len, look[2] / look_len ]

    # s = normalize(cross(f, up2))
    s = [
        f[1] * up_norm[2] - f[2] * up_norm[1],
        f[2] * up_norm[0] - f[0] * up_norm[2],
        f[0] * up_norm[1] - f[1] * up_norm[0]
    ]
    s_len = math.sqrt(s[0] * s[0] + s[1] * s[1] + s[2] * s[2]);
    s[0] /= s_len;
    s[1] /= s_len;
    s[2] /= s_len;

    # u = normalize(cross(normalize(s), f))
    u =[
        s[1] * f[2] - s[2] * f[1],
        s[2] * f[0] - s[0] * f[2],
        s[0] * f[1] - s[1] * f[0]
    ]
    u_len = math.sqrt(u[0] * u[0] + u[1] * u[1] + u[2] * u[2]);
    u[0] /= u_len;
    u[1] /= u_len;
    u[2] /= u_len;

    #if ( not (flags and ARCBALL_CAMERA_LEFT_HANDED_BIT))
    if( not flags):
        # in a right-handed coordinate system, the camera's z looks away from the look direction.
        # this gets flipped again later when you multiply by a right-handed projection matrix
        # (notice the last row of gluPerspective, which makes it back into a left-handed system after perspective division)
        f[0] = -f[0];
        f[1] = -f[1];
        f[2] = -f[2];

    # t = [s;u;f] * -eye
    t = [
        s[0] * -eye[0] + s[1] * -eye[1] + s[2] * -eye[2],
        u[0] * -eye[0] + u[1] * -eye[1] + u[2] * -eye[2],
        f[0] * -eye[0] + f[1] * -eye[1] + f[2] * -eye[2]
    ]

    # m = [s,t[0]; u,t[1]; -f,t[2]];
    view = [0,0,0,0 ,0,0,0,0, 0,0,0,0, 0,0,0,0]
    view[0] = s[0];
    view[1] = u[0];
    view[2] = f[0];
    view[3] = 0.0;
    view[4] = s[1];
    view[5] = u[1];
    view[6] = f[1];
    view[7] = 0.0;
    view[8] = s[2];
    view[9] = u[2];
    view[10] = f[2];
    view[11] = 0.0;
    view[12] = t[0];
    view[13] = t[1];
    view[14] = t[2];
    view[15] = 1.0;

    return view
# * eye:
#     * Current eye position. Will be updated to new eye position.
# * target:
#     * Current look target position. Will be updated to new position.
# * up:
#     * Camera's "up" direction. Will be updated to new up vector.
# * view (optional):
#     * The matrix that will be updated with the new view transform. Previous contents don't matter.
# * delta_time_seconds:
#     * Amount of seconds passed since last update.
# * zoom_per_tick:
#     * How much the camera should zoom with every scroll wheel tick.
# * pan_speed:
#     * How fast the camera should pan when holding middle click.
# * rotation_multiplier:
#     * For amplifying the rotation speed. 1.0 means 1-1 mapping between arcball rotation and camera rotation.
# * screen_width/screen_height:
#     * Dimensions of the screen the camera is being used in (the window size).
# * x0, x1:
#     * Previous and current x coordinate of the mouse, respectively.
# * y0, y1:
#     * Previous and current y coordinate of the mouse, respectively.
# * midclick_held:
#     * Whether the middle click button is currently held or not.
# * rclick_held:
#     * Whether the right click button is currently held or not.
# * delta_scroll_ticks:
#     * How many scroll wheel ticks passed since the last update (signed number)
# * flags:
#     * For producing a different view matrix depending on your conventions.

def arcball_camera_update(
    eye,
    target,
    up,
    delta_time_seconds,
    zoom_per_tick,
    pan_speed,
    rotation_multiplier,
    screen_width, screen_height,
    px_x0, px_x1,
    px_y0, px_y1,
    midclick_held,
    rclick_held,
    delta_scroll_ticks,
    flags
    ):
    # check preconditions
    
    up_len = math.sqrt(up[0] * up[0] + up[1] * up[1] + up[2] * up[2]);
    
    to_target = [
        target[0] - eye[0],
        target[1] - eye[1],
        target[2] - eye[2],
    ]
    to_target_len = math.sqrt(to_target[0] * to_target[0] + to_target[1] * to_target[1] + to_target[2] * to_target[2]);
    

    # right click is held, then mouse movements implement rotation.
    if (rclick_held):
        x0 = (float)(px_x0 - screen_width / 2);
        x1 = (float)(px_x1 - screen_width / 2);
        y0 = (float)(px_y0 - screen_height / 2);
        y1 = (float)(px_y1 - screen_height / 2);
        arcball_radius = (float)(screen_width if screen_width > screen_height else screen_height);

        # distances to center of arcball
        dist0 = math.sqrt(x0 * x0 + y0 * y0);
        dist1 = math.sqrt(x1 * x1 + y1 * y1);

        z0 = 0.0;
        if (dist0 <= arcball_radius):
            # compute depth of intersection using good old pythagoras
            z0 = math.sqrt(arcball_radius * arcball_radius - x0 * x0 - y0 * y0);
        
            z1=0.0;
            if (dist1 > arcball_radius):
                # started inside the ball but went outside, so clamp it.
                x1 = (x1 / dist1) * arcball_radius;
                y1 = (y1 / dist1) * arcball_radius;
                dist1 = arcball_radius;
                z1 = 0.0;
            else:
                # compute depth of intersection using good old pythagoras
                z1 = math.sqrt(arcball_radius * arcball_radius - x1 * x1 - y1 * y1);

            # rotate intersection points according to where the eye is

            to_eye_unorm = [
                eye[0] - target[0],
                eye[1] - target[1],
                eye[2] - target[2]
            ];
            to_eye_len = math.sqrt(to_eye_unorm[0] * to_eye_unorm[0] + to_eye_unorm[1] * to_eye_unorm[1] + to_eye_unorm[2] * to_eye_unorm[2]);
            to_eye = [
                to_eye_unorm[0] / to_eye_len,
                to_eye_unorm[1] / to_eye_len,
                to_eye_unorm[2] / to_eye_len
            ]

            across = [
                -(to_eye[1] * up[2] - to_eye[2] * up[1]),
                -(to_eye[2] * up[0] - to_eye[0] * up[2]),
                -(to_eye[0] * up[1] - to_eye[1] * up[0])
            ]

            # matrix that transforms standard coordinates to be relative to the eye
            eye_m = [
                across[0], across[1], across[2],
                up[0], up[1], up[2],
                to_eye[0], to_eye[1], to_eye[2]
            ]

            new_p0 = [
                eye_m[0] * x0 + eye_m[3] * y0 + eye_m[6] * z0,
                eye_m[1] * x0 + eye_m[4] * y0 + eye_m[7] * z0,
                eye_m[2] * x0 + eye_m[5] * y0 + eye_m[8] * z0,
            ]

            new_p1 = [
                eye_m[0] * x1 + eye_m[3] * y1 + eye_m[6] * z1,
                eye_m[1] * x1 + eye_m[4] * y1 + eye_m[7] * z1,
                eye_m[2] * x1 + eye_m[5] * y1 + eye_m[8] * z1,
            ]

            x0 = new_p0[0];
            y0 = new_p0[1];
            z0 = new_p0[2];

            x1 = new_p1[0];
            y1 = new_p1[1];
            z1 = new_p1[2];

            # compute quaternion between the two vectors (http:#lolengine.net/blog/2014/02/24/quaternion-from-two-vectors-final)
            qw = qx = qy = qz = 0.0
            norm_u_norm_v = math.sqrt((x0 * x0 + y0 * y0 + z0 * z0) * (x1 * x1 + y1 * y1 + z1 * z1));
            qw = norm_u_norm_v + (x0 * x1 + y0 * y1 + z0 * z1);

            if (qw < 0.00001 * norm_u_norm_v):
                qw = 0.0;
                if (fabsf(x0) > fabsf(z0)):
                    qx = -y0;
                    qy = x0;
                    qz = 0.0;
                else:
                    qx = 0.0;
                    qy = -z0;
                    qz = y0;
            else:
                qx = y0 * z1 - z0 * y1;
                qy = z0 * x1 - x0 * z1;
                qz = x0 * y1 - y0 * x1;


            q_len = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw);
            qx /= q_len;
            qy /= q_len;
            qz /= q_len;
            qw /= q_len;


            # amplify the quaternion's rotation by the multiplier
            # this is done by slerp(Quaternion.identity, q, multiplier)
            # math from http:#number-none.com/product/Understanding%20Slerp,%20Then%20Not%20Using%20It/

            # cos(angle) of the quaternion
            c = qw;
            if (c > 0.9995):
                # if the angle is small, linearly interpolate and normalize.
                qx = rotation_multiplier * qx;
                qy = rotation_multiplier * qy;
                qz = rotation_multiplier * qz;
                qw = 1.0 + rotation_multiplier * (qw - 1.0);
                q_len = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw);
                qx /= q_len;
                qy /= q_len;
                qz /= q_len;
                qw /= q_len;

            else:
                # clamp to domain of acos for robustness
                if (c < -1.0):
                    c = -1.0;
                elif (c > 1.0):
                    c = 1.0;
                # angle of the initial rotation
                theta_0 = math.acos(c);
                # apply multiplier to rotation
                theta = theta_0 * rotation_multiplier;

                # compute the quaternion normalized difference
                qx2 = qx;
                qy2 = qy;
                qz2 = qz;
                qw2 = qw - c;
                q2_len = math.sqrt(qx2 * qx2 + qy2 * qy2 + qz2 * qz2 + qw2 * qw2);
                qx2 /= q2_len;
                qy2 /= q2_len;
                qz2 /= q2_len;
                qw2 /= q2_len;

                # do the slerp
                qx = qx2 * math.sin(theta);
                qy = qy2 * math.sin(theta);
                qz = qz2 * math.sin(theta);
                qw = math.cos(theta) + qw2 * math.sin(theta);

            # vector from the target to the eye, which will be rotated according to the arcball's arc.
            to_eye = [eye[0] - target[0], eye[1] - target[1], eye[2] - target[2] ]

            # convert quaternion to matrix (note: row major)
            qmat = [
                (1.0 - 2.0 * qy * qy - 2.0 * qz * qz), 2.0 * (qx * qy + qw * qz), 2.0 * (qx * qz - qw * qy),
                2.0 * (qx * qy - qw * qz), (1.0 - 2.0 * qx * qx - 2.0 * qz * qz), 2.0 * (qy * qz + qw * qx),
                2.0 * (qx * qz + qw * qy), 2.0 * (qy * qz - qw * qx), (1.0 - 2.0 * qx * qx - 2.0 * qy * qy)
            ]

            # compute rotated vector
            to_eye2 = [
                to_eye[0] * qmat[0] + to_eye[1] * qmat[1] + to_eye[2] * qmat[2],
                to_eye[0] * qmat[3] + to_eye[1] * qmat[4] + to_eye[2] * qmat[5],
                to_eye[0] * qmat[6] + to_eye[1] * qmat[7] + to_eye[2] * qmat[8]
            ]

            # compute rotated up vector
            up2 = [
                up[0] * qmat[0] + up[1] * qmat[1] + up[2] * qmat[2],
                up[0] * qmat[3] + up[1] * qmat[4] + up[2] * qmat[5],
                up[0] * qmat[6] + up[1] * qmat[7] + up[2] * qmat[8]
            ]

            up2_len = math.sqrt(up2[0] * up2[0] + up2[1] * up2[1] + up2[2] * up2[2]);
            up2[0] /= up2_len;
            up2[1] /= up2_len;
            up2[2] /= up2_len;

            # update eye position
            eye[0] = target[0] + to_eye2[0];
            eye[1] = target[1] + to_eye2[1];
            eye[2] = target[2] + to_eye2[2];

            # update up vector
            up[0] = up2[0];
            up[1] = up2[1];
            up[2] = up2[2];
    

    #label .end_rotate

    # if midclick is held, then mouse movements implement translation
    if (midclick_held):
        dx = (int)(px_x0 - px_x1);
        dy = (int)((px_y0 - px_y1));

        to_eye_unorm = [
            eye[0] - target[0],
            eye[1] - target[1],
            eye[2] - target[2]
        ]
        to_eye_len = math.sqrt(to_eye_unorm[0] * to_eye_unorm[0] + to_eye_unorm[1] * to_eye_unorm[1] + to_eye_unorm[2] * to_eye_unorm[2]);
        to_eye = [
            to_eye_unorm[0] / to_eye_len,
            to_eye_unorm[1] / to_eye_len,
            to_eye_unorm[2] / to_eye_len
        ]

        across = [
            -(to_eye[1] * up[2] - to_eye[2] * up[1]),
            -(to_eye[2] * up[0] - to_eye[0] * up[2]),
            -(to_eye[0] * up[1] - to_eye[1] * up[0])
        ]

        pan_delta = [
            delta_time_seconds * pan_speed * (dx * across[0] + dy * up[0]),
            delta_time_seconds * pan_speed * (dx * across[1] + dy * up[1]),
            delta_time_seconds * pan_speed * (dx * across[2] + dy * up[2]),
        ]

        eye[0] += pan_delta[0];
        eye[1] += pan_delta[1];
        eye[2] += pan_delta[2];
        
        target[0] += pan_delta[0];
        target[1] += pan_delta[1];
        target[2] += pan_delta[2];

    # compute how much scrolling happened
    zoom_dist = zoom_per_tick * delta_scroll_ticks;

    # the direction that the eye will move when zoomed
    to_target=[
        target[0] - eye[0],
        target[1] - eye[1],
        target[2] - eye[2],
    ]

    to_target_len = math.sqrt(to_target[0] * to_target[0] + to_target[1] * to_target[1] + to_target[2] * to_target[2]);

    # if the zoom would get you too close, clamp it.
    if (not rclick_held):
        if (zoom_dist >= to_target_len - 0.001):
            zoom_dist = to_target_len - 0.001;


    # normalize the zoom direction
    look=[
        to_target[0] / to_target_len,
        to_target[1] / to_target_len,
        to_target[2] / to_target_len,
    ]

    eye_zoom=[
        look[0] * zoom_dist,
        look[1] * zoom_dist,
        look[2] * zoom_dist
    ]

    eye[0] += eye_zoom[0];
    eye[1] += eye_zoom[1];
    eye[2] += eye_zoom[2];

    if (rclick_held):
        # affect target too if right click is held
        # this allows you to move forward and backward (as opposed to zoom)
        target[0] += eye_zoom[0];
        target[1] += eye_zoom[1];
        target[2] += eye_zoom[2];
    

    return arcball_camera_look_to(eye, look, up, flags);

