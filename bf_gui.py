# Shoutout to Stuntlover, SaiMoen, and Shweetz

import colorsys
import ctypes
import math
import os
import signal
import struct
import sys
import threading
import time
import json

from bf_specific import GoalSpeed, GoalNosepos, GoalHeight, GoalPoint

try:
    import numpy as np
    import glfw
    import imgui
    import requests
    import numpy
    import OpenGL.GL as gl
    import win32api

    from imgui.integrations.glfw import GlfwRenderer

    from tminterface.structs import BFEvaluationDecision, BFEvaluationInfo, BFEvaluationResponse, BFPhase
    from tminterface.interface import TMInterface
    from tminterface.client import Client
except ImportError:
    print("Failed to import modules, trying to install...")
    os.system("python -m pip install -r requirements.txt")
    print("Installed requirements")

class Global:
    """Add your variables you want to use globally in here"""

    def __init__(self):
        self.is_registered = False
        self.server = ""

        # Goal
        self.current_goal = 0 # 0 Speed, 1 Nosepos, 2 Height, 3 Point
        self.strategy = "any"
        self.extra_yaw = 0
        self.point = [0, 0, 0]
        self.time_min = 0
        self.time_max = 0

        # Conditions
        self.enablePositionCheck = False
        self.enableYawCheck = False
        self.triggerCorner1 = [0, 0, 0]
        self.triggerCorner2 = [999, 999, 999]
        self.minYaw = 0.000
        self.maxYaw = 999.000
        self.min_speed_kmh = 0
        self.min_cp = 0
        self.must_touch_ground = False

        # Result
        self.current_best = -1
        self.improvement_time = 0
        self.improvements = 0
        self.position = [0, 0, 0]
        self.velocity = [0, 0, 0]
        self.rotation = [0, 0, 0]

        # Saving Inputs
        self.save_inputs = False
        self.save_folder = "current"
        self.save_only_results = False

        # Other
        self.settings_file_name = "settings.json"
        self.improvements_list = [0.0]
        self.improvement_graph = False
        self.improvement_graph_scale = 0

        # Updates
        self.version_file_url = 'https://raw.githubusercontent.com/CodyNinja1/TMIBruteforceGUI/main/bf_gui_version.txt' # This should always stay the same
        self.version_file_lines = requests.get(self.version_file_url).text.split("\n")
        self.version = (self.version_file_lines[0][:30] + "...") if len(self.version_file_lines[0]) > 30 else self.version_file_lines[0]
        self.current_version = "v0.1.3.7-patch"

    def unpackCoordinates(self):
        """Execute only once, on simulation start"""
        (self.minX, self.maxX), (self.minY, self.maxY), (self.minZ, self.maxZ) = [
            sorted((round(self.triggerCorner1[i], 2), round(self.triggerCorner2[i], 2))) for i in range(3)
        ]

    def isCarInTrigger(self, state):
        """Execute every tick where is_eval_time() is True"""
        car_x, car_y, car_z = state.position
        return self.minX <= car_x <= self.maxX and self.minY <= car_y <= self.maxY and self.minZ <= car_z <= self.maxZ
    
    def isCarInMinMaxYaw(self):
        yaw = g.rotation[0]
        return g.minYaw <= yaw <= g.maxYaw


    def save_settings(self, filename):
        """Save bruteforce settings, takes filename as an argument"""
        settings = {
            "current_goal": g.current_goal,
            "extra_yaw": g.extra_yaw,
            "point": g.point,

            "enablePositionCheck": g.enablePositionCheck,
            "triggerCorner1": g.triggerCorner1,
            "triggerCorner2": g.triggerCorner2,
            "minYaw": g.minYaw,
            "maxYaw": g.maxYaw,

            "save_inputs": g.save_inputs,
            "save_folder": g.save_folder,
            "save_only_results": g.save_only_results,

            "time_min": g.time_min,
            "time_max": g.time_max,
            "min_speed_kmh": g.min_speed_kmh,
            "min_cp": g.min_cp,
            "must_touch_ground": g.must_touch_ground,
            "settings_file_name": g.settings_file_name,
            "improvement_graph": g.improvement_graph
        }

        with open(filename, "w") as s:
            json.dump(settings, s, sort_keys=True, indent=4)

    def load_settings(self, filename):
        """Load bruteforce settings, takes filename as an argument"""
        with open(filename, "r") as set:
            settings = json.load(set)

            g.current_goal = settings["current_goal"]
            g.extra_yaw = settings["extra_yaw"]
            g.point = settings["point"]

            g.enablePositionCheck = settings["enablePositionCheck"]
            g.triggerCorner1 = settings["triggerCorner1"]
            g.triggerCorner2 = settings["triggerCorner2"]
            g.minYaw = settings["minYaw"]
            g.maxYaw = settings["maxYaw"]

            g.save_inputs = settings["save_inputs"]
            g.save_folder = settings["save_folder"]
            g.save_only_results = settings["save_only_results"]

            g.time_min = settings["time_min"]
            g.time_max = settings["time_max"]
            g.min_speed_kmh = settings["min_speed_kmh"]
            g.min_cp = settings["min_cp"]
            g.must_touch_ground = settings["must_touch_ground"]
            g.settings_file_name = settings["settings_file_name"]
            g.improvement_graph = settings["improvement_graph"]

g = Global()

def update():
    """
    Prompts user to update if they are on an out of date version, automatically replaces old files
    Returns 0 if it was updated, 1 if not, 2 if there was a new update but the user declined it
    """
    accepted_update = None 

    ICON_INFO = 0x40
    ICON_WARNING = 0x30
    MB_OK = 0x0
    MB_YESNO = 0x4

    print("Checking for updates...")
    if g.version != g.current_version:
        print(f"Found new update, new version: {g.version}, current version: {g.current_version}")
        accepted_update = ctypes.windll.user32.MessageBoxW(0, f"New update available! Would you like to install the newest version?\n(Warning: This will replace any code you have changed)", f"{g.version} Version Available!", ICON_WARNING | MB_YESNO)
    

    if accepted_update == 6:
        download = lambda file_name, file_url : open(file_name, 'wb').write(file_url.content)

        download("bf_gui.py", requests.get(g.version_file_lines[1]))
        download("bf_specific.py", requests.get(g.version_file_lines[2]))
        download("requirements.txt", requests.get(g.version_file_lines[3]))

        ctypes.windll.user32.MessageBoxW(0, "Done updating, all necessary files have been replaced\nPlease reopen the program", "Update Complete", MB_OK | ICON_INFO)

        return 0

    elif accepted_update == 7: return 2

    else: return 1

updated = update()

if updated == 0:
    print("Updated, exiting program")
    exit()

elif updated == 1:
    print("No updates found, running TMIBruteforceGUI")

elif updated == 2:
    print("Declined update")


try:
    g.load_settings("autosave.json")
except:
    if not os.path.exists("autosave.json"):
        with open("autosave.json", "x") as autosave:
            g.save_settings("autosave.json")

def makeGUI():
    GUI()

def h2r(h, s, v, a):
    # hsva values must be [0, 1] range
    out = list(colorsys.hsv_to_rgb(h*255, s*255, v*255))
    out.append(a)
    return [out[0]/255, out[1]/255, out[2]/255, out[3]]

def r2h(r, g, b, a):
    # rgba values must be [0, 1] range
    out = list(colorsys.rgb_to_hsv(r*255, g*255, b*255))
    out.append(a)
    return [out[0]/255, out[1]/255, out[2]/255, out[3]]

def pushStyleColor(style, color):
    imgui.push_style_color(style, color[0], color[1], color[2], color[3])

def to_rad(deg):
    return deg / 180 * math.pi

def to_deg(rad):
    return rad * 180 / math.pi

def get_nb_cp(state):
    return len([time for time, _ in state.cp_data.cp_times if time != -1])

WHEEL_OFFSETS = tuple([(3056 // 4) * i for i in range(4)])
def nb_wheels_on_ground(state):
    return sum([struct.unpack('i', state.simulation_wheels[o+292:o+296])[0] for o in WHEEL_OFFSETS])

class MainClient(Client):
    def __init__(self) -> None:
        super().__init__()
        self.time = -1
        self.finished = False
        self.goal = GoalSpeed()

    def on_registered(self, iface: TMInterface) -> None:
        print(f'Registered to {iface.server_name}')
        g.is_registered = True
        g.server = iface.server_name

    def on_deregistered(self, iface: TMInterface):
        print(f'Deregistered from {iface.server_name}')
        g.is_registered = False

    def on_simulation_begin(self, iface):
        iface.execute_command('set controller bruteforce')

        self.lowest_time = iface.get_event_buffer().events_duration
        self.time = -1
        self.current = -1
        self.iterations = 0
        g.current_best = -1
        g.improvement_time = -1
        g.improvements = 0
        g.improvements_list = [0.0]

        g.unpackCoordinates()
        if g.current_goal == 0: self.goal = GoalSpeed()
        if g.current_goal == 1: self.goal = GoalNosepos()
        if g.current_goal == 2: self.goal = GoalHeight()
        if g.current_goal == 3: self.goal = GoalPoint()

    def on_bruteforce_evaluate(self, iface, info: BFEvaluationInfo) -> BFEvaluationResponse:
        self.time = info.time
        self.phase = info.phase

        response = BFEvaluationResponse()
        response.decision = BFEvaluationDecision.DO_NOTHING

        if g.time_min > self.time: # early return
            return response

        self.state = iface.get_simulation_state()

        # Initial phase (base run + after every ACCEPT improvement)
        # Check the all the ticks in eval_time and print the best one when run is in last tick of eval_time
        if self.phase == BFPhase.INITIAL:
            if self.is_eval_time() and self.is_better():
                g.current_best = self.current
                g.improvement_time = round(self.time/1000, 2)
                g.position = [round(pos, 3) for pos in self.state.position]
                g.velocity = [round(vel, 3) for vel in self.state.velocity]
                g.rotation = [round(to_deg(ypr), 3) for ypr in self.state.yaw_pitch_roll]

            if self.is_max_time():
                self.goal.print(g)

        # Search phase only impacts decision, logic is in initial phase
        elif self.phase == BFPhase.SEARCH:
            if self.is_eval_time() and self.is_better():
                response.decision = BFEvaluationDecision.ACCEPT
                g.improvements += 1
                g.improvements_list.append(float(g.current_best)) # float because imgui doesn't like ints (racist)
                self.iterations += 1
                if g.save_inputs:
                    self.save_result(filename=f"improvement_{g.improvements}.txt", event_buffer=iface.get_event_buffer())

            elif self.is_past_eval_time():
                response.decision = BFEvaluationDecision.REJECT
                self.iterations += 1
                if g.save_inputs and not g.save_only_results:
                    self.save_result(filename=f"iteration_{self.iterations}.txt", event_buffer=iface.get_event_buffer())

        return response

    def is_better(self):

        # Conditions
        if g.min_speed_kmh > numpy.linalg.norm(self.state.velocity) * 3.6: # Min speed
            return False

        if g.min_cp > get_nb_cp(self.state): # Min CP
            return False

        if g.must_touch_ground and nb_wheels_on_ground(self.state) == 0: # Touch ground
            return False

        if g.enablePositionCheck and not g.isCarInTrigger(self.state): # Position
            return False
        
        if g.enableYawCheck and not g.isCarInMinMaxYaw(): # Yaw
            return False

        # Specific goal bruteforce
        # This line is a bit complicated, but for example, for speed it means: GoalSpeed.is_better(MainClient, g)
        return self.goal.is_better(self, g)

    def is_eval_time(self):
        return g.time_min <= self.time <= g.time_max

    def is_past_eval_time(self):
        return self.time > g.time_max

    def is_max_time(self):
        return self.time == g.time_max

    def on_checkpoint_count_changed(self, iface: TMInterface, current: int, target: int):
        if current == target:
            self.finished = True

    def save_result(self, filename: str, event_buffer):
        # event_buffer is type EventBufferData

        # Find TMInterface/Scripts/
        scripts_dir = os.path.join(os.path.expanduser('~'), "Documents", "TMInterface", "Scripts")
        if not os.path.isdir(scripts_dir):
            # try OneDrive path
            scripts_dir = os.path.join(os.path.expanduser('~'), "OneDrive", "Documents", "TMInterface", "Scripts")
            if not os.path.isdir(scripts_dir):
                print("ERROR: path to Scripts/ not found.")
                return

        # Find or create directory to save inputs in this bruteforce session
        session_dir = os.path.join(scripts_dir, g.save_folder)
        if not os.path.isdir(session_dir):
            os.mkdir(session_dir)

        # Write inputs to a file
        filepath = os.path.join(session_dir, filename)
        with open(filepath, "w") as f:
            f.write(event_buffer.to_commands_str())

class GUI:
    def __init__(self):
        self.fontPath = "" # font
        self.color = [0.25, 0.5, 0.75, 0.5] # background color
        self.bgcolor = [0.25, 0.5, 0.75, 0.5] # this is from glfw (don't ask ok)
        self.colorChange = 0 # you can change this if you want
        self.rgbScroll = False # rgb background flag
        self.enableExtraYaw = False
        self.goals = ["Speed", "Nosebug position", "Height", "Minimum distance from point"]
        self.backgroundColor = [0.25, 0.5, 0.75, 0.5]

        self.settings = {
            "font": self.fontPath,
            "color": self.color,
            "rgb_speed": self.colorChange,
            "rgb_e": self.rgbScroll,
            "yaw_e": self.enableExtraYaw,
            "yaw": g.extra_yaw,
            "coordsCheck": g.enablePositionCheck,
            "triggerCorner1": g.triggerCorner1,
            "triggerCorner2": g.triggerCorner2,
            "point": g.point,
            "bf_goal": g.current_goal
        }

        self.window = self.impl_glfw_init(width=700, height=500)
        gl.glClearColor(*self.backgroundColor)
        imgui.create_context()
        self.impl = GlfwRenderer(self.window)
        if self.fontPath:
            io = imgui.get_io()
            io.fonts.clear()
            io.font_global_scale = 1
            new_font = io.fonts.add_font_from_file_ttf(self.fontPath, 20, io.fonts.get_glyph_ranges_latin())
            self.impl.refresh_font_texture()

        self.loop()

    def impl_glfw_init(self, window_name=f"TrackMania Bruteforce GUI {g.current_version}", width=300, height=300):
        if not glfw.init():
            print("Could not initialize OpenGL context")
            exit(1)

        # OS X supports only forward-compatible core profiles from 3.2
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)

        # Create a windowed mode window and its OpenGL context
        window = glfw.create_window(int(width), int(height), window_name, None, None)
        glfw.make_context_current(window)

        # glfw.set_window_opacity(window, 0.5)
        # glfw.set_window_attrib(window, glfw.DECORATED, False)

        if not window:
            glfw.terminate()
            print("Could not initialize Window")
            exit(1)

        return window

    def bf_speed_gui(self):
        pass

    def bf_height_gui(self):
        pass

    def bf_nose_gui(self):
        self.enableExtraYaw = imgui.checkbox("Enable Custom Yaw Value", self.enableExtraYaw)[1]

        if self.enableExtraYaw:
            g.strategy = "custom"
            g.extra_yaw = imgui.input_float('Yaw', g.extra_yaw)[1]
        else:
            g.strategy = "any"

    def bf_point_gui(self):
        g.point = imgui.input_float3('Point Coordinates', *g.point)[1]

    def bf_conditions_gui(self):
        g.min_speed_kmh = imgui.input_int('Minimum Speed (km/h)', g.min_speed_kmh)[1]
        g.min_cp = imgui.input_int('Minimum Checkpoints', g.min_cp)[1]
        g.must_touch_ground = imgui.checkbox("Must touch ground", g.must_touch_ground)[1]

        # Position Check
        g.enablePositionCheck = imgui.checkbox("Enable Position check (Car must be inside Trigger)", g.enablePositionCheck)[1]

        if g.enablePositionCheck:
            input_pair = lambda s, pair: imgui.input_float3(s, *pair)[1]
            g.triggerCorner1, g.triggerCorner2 = input_pair('Trigger Corner 1', g.triggerCorner1), input_pair('Trigger Corner 2', g.triggerCorner2)
        
        # Yaw Check
        g.enableYawCheck = imgui.checkbox("Enable Yaw Check (Car must be between 2 Yaw values)", g.enableYawCheck)[1]
        
        if g.enableYawCheck:
            g.minYaw = imgui.input_float('Minimum Yaw', g.minYaw)[1]
            g.maxYaw = imgui.input_float('Maximum Yaw', g.maxYaw)[1]
            print(g.minYaw, g.maxYaw)

    def bf_other_gui(self):
        g.save_inputs = imgui.checkbox("Save inputs of every iteration and/or improvements separately in a folder", g.save_inputs)[1]
        if g.save_inputs:
            g.save_folder = imgui.input_text('Folder Name', g.save_folder, 256)[1]
            g.save_only_results = imgui.checkbox("Save only improvements separately", g.save_only_results)[1]

    def save_settings_gui(self):
        save = imgui.button("Save Settings")
        if save:
            g.save_settings(g.settings_file_name)

    def load_settings_gui(self):
        load = imgui.button("Load Settings")
        if load:
            g.load_settings(g.settings_file_name)

    def settings_file_name_gui(self):
        g.settings_file_name = imgui.input_text("Settings File Name", g.settings_file_name, 256)[1] 

    def bf_settings(self):
        imgui.begin("Evaluation Settings", True)

        imgui.text("Goal and parameters")
        g.current_goal = imgui.combo("Bruteforce Goal", g.current_goal, self.goals)[1]
        if   g.current_goal == 0: self.bf_speed_gui()
        elif g.current_goal == 1: self.bf_nose_gui()
        elif g.current_goal == 2: self.bf_height_gui()
        elif g.current_goal == 3: self.bf_point_gui()

        imgui.separator()

        imgui.text("Evaluation time")
        timetext = lambda s, t: round(imgui.input_float(s, t/1000)[1] * 1000, 3)
        g.time_min = timetext("Evaluation start (s)", g.time_min)
        g.time_max = timetext("Evaluation end (s)", g.time_max)
        if g.time_min > g.time_max:
            g.time_max = g.time_min

        imgui.separator()

        imgui.text("Conditions")
        self.bf_conditions_gui()

        imgui.separator()

        imgui.text("Other")
        self.bf_other_gui()

        imgui.separator()

        imgui.text("Settings")
        self.save_settings_gui()
        self.load_settings_gui()
        self.settings_file_name_gui()

        imgui.end()

    def bf_result(self):
        # thanks shweetz
        # this is to clarify what unit of measurement is currently used
        if   g.current_goal == 0: unit = "(km/h)" # Speed
        elif g.current_goal == 1: unit = "(degrees)" # Nosepos
        else:                     unit = "(m)" # Point/Height

        imgui.begin("Bruteforce Info", True)

        imgui.text("Connection Status: " + (f"Connected to {g.server}" if g.is_registered else "Not Registered"))
        imgui.separator()

        best = g.current_best
        if g.current_goal == 3 and best > 0: # Point
            best = math.sqrt(best)
        imgui.text(f"Bruteforce Best: {round(best, 3)} {unit}")

        imgui.text(f"Improvements: {g.improvements}")
        imgui.text(f"Car information at {g.improvement_time}:")

        imgui.separator()

        imgui.text(f"Position (x, y, z): {g.position}")
        imgui.text(f"Velocity (x, y, z): {g.velocity}")
        imgui.text(f"Rotation (yaw, pitch, roll): {g.rotation}")

        imgui.separator()
        
        g.improvement_graph = imgui.checkbox("Enable improvement graph", g.improvement_graph)[1]

        imgui.end()

    def bf_improvement_graph(self):
        if not g.improvement_graph:
            pass
        else:
            imgui.begin("Improvement Graph", True)
            # The "##" is to make the name disappear, it is used to clarify what this plot is for in code.    
            improvement = g.improvements_list[len(g.improvements_list)-1]
            if improvement > g.improvement_graph_scale: g.improvement_graph_scale = improvement
            imgui.plot_lines(
                "##Improvement Graph", 
                np.array(g.improvements_list, np.float32), 
                graph_size=(700, 400),
                scale_max=g.improvement_graph_scale 
            )
            
            imgui.end()


    def customize(self):
        imgui.begin("Customize", True)

        if imgui.button("Start RGB scroll" if not self.rgbScroll else "Stop RGB Scroll"):
            self.rgbScroll = not self.rgbScroll

        if self.rgbScroll:
            if not any(self.color[:3]): self.color = [(i + 1) / 4 for i in range(4)]
            self.colorChange = imgui.slider_float(
                "Speed", self.colorChange,
                min_value=0, max_value=32,
                power=1
            )[1]

        else:
            self.color = list(imgui.color_edit4("Background", *self.color, show_alpha=False)[1])
            self.backgroundColor = self.color.copy()

        imgui.end()

    def loop(self):
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            self.impl.process_inputs()
            imgui.new_frame()

            self.bf_result()
            self.bf_settings()
            self.bf_improvement_graph()
            self.customize()

            imgui.render()

            if self.rgbScroll:
                self.color = r2h(*self.color) # convert to hsv
                self.color[0] = (self.color[0] + self.colorChange/1000000) % 1 # add hue (division is because of very high FPS)
                self.color = h2r(*self.color) # convert back into rgb

            self.backgroundColor = self.color.copy() # set the self.color

            gl.glClearColor(*self.backgroundColor)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)

            self.impl.render(imgui.get_draw_data())
            glfw.swap_buffers(self.window)

        self.impl.shutdown()
        glfw.terminate()

        g.save_settings("autosave.json")
        exit()

def main():
    server_name = f'TMInterface{sys.argv[1]}' if len(sys.argv) > 1 else 'TMInterface0'
    print(f'Connecting to {server_name}...')
    client = MainClient()
    iface = TMInterface(server_name)

    def handler(signum, frame):
        iface.close()
        quit()

    def on_exit(signal_type):
        g.save_settings("autosave.json")
    
    win32api.SetConsoleCtrlHandler(on_exit, True)

    signal.signal(signal.SIGBREAK, handler)
    signal.signal(signal.SIGINT, handler)
    iface.register(client)

    while not iface.registered:
        time.sleep(0)

    while iface.registered:
        time.sleep(0)

if __name__ == '__main__':
    GUI_thread = threading.Thread(target=makeGUI, daemon=True)
    GUI_thread.start()

    main()
