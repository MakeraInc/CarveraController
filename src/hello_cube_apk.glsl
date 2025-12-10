---vertex
$HEADER$
#ifdef GL_ES
    precision highp float;
#endif
attribute vec3 my_vertex_position;
attribute vec3 color_att;
attribute float type;
attribute float vertex_id;
attribute float distance_id;
attribute float vertex_tool;

uniform mat4 center_the_cube;
uniform mat4 my_rotation;
uniform mat4 my_view;
uniform mat4 my_proj;

varying vec3 vs_color;
varying float vs_vertex_id;
varying float vs_distance_id;
varying float vs_vertex_type;
void main()
{
    vs_color = color_att;
    vs_vertex_id = vertex_id;
    vs_vertex_type = vertex_tool;//type;

    vs_distance_id = distance_id;

    if(vertex_id<0.0)
        gl_Position = my_proj * my_view * 
                //move point to display center
                center_the_cube * vec4(my_vertex_position,1);
    else
        gl_Position = my_proj * my_view * my_rotation *
                //move point to display center
                center_the_cube * vec4(my_vertex_position,1);
}

---fragment
$HEADER$
#ifdef GL_ES
    precision highp float;
#endif

varying vec3 vs_color;
varying float vs_vertex_id;
varying float vs_distance_id;
varying float vs_vertex_type;

uniform float display_count;
//FUCK: cannot be int in FUCKING KIVY
uniform float vertex_type_display;
//out vec3 fs_color;
void main()
{
    //dynamic displaying
    if(display_count>-1.0 && vs_distance_id > display_count)
        discard;
    //vertex type display
    //avoid float bias
    int fs_vertex_type = int(vs_vertex_type + 0.1);
    int fs_vertex_type_display = int(vertex_type_display+0.1);
    //pass if fs_vertex_type_display == 0
    if(fs_vertex_type_display>0)
    {
        
        //if(0==(fs_vertex_type & fs_vertex_type_display))
        //    discard;

        //FUCK OPENGLES
        int class8 = int(fs_vertex_type_display/10000000);fs_vertex_type_display -= class8*10000000;
        int class7 = int(fs_vertex_type_display/1000000);fs_vertex_type_display -= class7*1000000;
        int class6 = int(fs_vertex_type_display/100000);fs_vertex_type_display -= class6*100000;
        int class5 = int(fs_vertex_type_display/10000);fs_vertex_type_display -= class5*10000;
        int class4 = int(fs_vertex_type_display/1000);fs_vertex_type_display -= class4*1000;
        int class3 = int(fs_vertex_type_display/100);fs_vertex_type_display -= class3*100;
        int class2 = int(fs_vertex_type_display/10);fs_vertex_type_display -= class2*10;
        int class1 = int(fs_vertex_type_display);
        if(!(   (fs_vertex_type==7 && class7>0)||
                (fs_vertex_type==6 && class6>0)||
                (fs_vertex_type==5 && class5>0) || 
                (fs_vertex_type==4 && class4>0) ||
                (fs_vertex_type==3 && class3>0) ||
                (fs_vertex_type==2 && class2>0) ||
                (fs_vertex_type==1 && class1>0)))
            discard;
    }

    vec3 fs_color = vs_color;
    //no lerp color
    if(fs_color.r > 0.0) fs_color = vec3(1.0,0.0,0.0);
    gl_FragColor = vec4(fs_color,1.0)*texture2D(texture0, tex_coord0);
}