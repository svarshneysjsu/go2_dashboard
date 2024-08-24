
import os
import time
import json
import threading
import cv2
import openai
import numpy as np
from pathlib import Path
from prompt_toolkit import prompt
from flask import Flask, Response, render_template, redirect, url_for, jsonify, request, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import pyttsx3

# SDK libraries import
from unitree_sdk2py.idl.idl_dataclass import IDLDataClass
from unitree_sdk2py.core.dds.channel import DDSChannelFactoryInitialize
from unitree_sdk2py.utils.logger import setup_logging
from unitree_sdk2py.sdk.sdk import create_standard_sdk
from unitree_sdk2py.go2.audiohub.audiohub_client import AudioHubClient
from unitree_sdk2py.go2.video.video_client import VideoClient
from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.go2.vui.vui_client import VuiClient

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__, static_folder="static")
# app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'sounds'
app.config['UPLOAD_FOLDER_IMAGES'] = 'captured_images'
app.config['ALLOWED_EXTENSIONS'] = {'mp3', 'wav', 'ogg', 'aac', 'flac'}

script_process = {'process': None, 'name': None}
dog_data = {}

idl_data_class = IDLDataClass()

SportModeState_ = idl_data_class.get_data_class('SportModeState_')
LowState_ = idl_data_class.get_data_class('LowState_')

move_speed = 0.5
turn_speed = 1

def LowStateHandler(msg: LowState_):
    dog_data["voltage"] = format(msg.power_v, ".2f")
    dog_data["current"] = format(msg.power_a, ".2f")
    dog_data["avg temp"] = round((msg.temperature_ntc1 + msg.temperature_ntc2) / 2)

def HighStateHandler(msg: SportModeState_):
    dog_data["velocity x"] = format(msg.velocity[0], ".2f")
    dog_data["velocity y"] = format(msg.velocity[1], ".2f")
    dog_data["velocity z"] = format(msg.velocity[2], ".2f")
    dog_data["yaw spd"] = format(msg.yaw_speed, ".2f")

# For Getting the Logs
setup_logging(verbose=True)

# Initializing the SDK, Communicator and Robot
sdk = create_standard_sdk('UnitreeGo2SDK')
communicator = DDSChannelFactoryInitialize(domainId=0)
robot = sdk.create_robot(communicator, serialNumber='B42D4000O3M7MN8W') # This is the serial number for Go2 robot dog.clear

low_state_sub = communicator.ChannelSubscriber("rt/lowstate", LowState_)
low_state_sub.Init(LowStateHandler, 10)

high_state_sub = communicator.ChannelSubscriber("rt/sportmodestate", SportModeState_)
high_state_sub.Init(HighStateHandler, 10)

# Initializing the robot clients
audio_client: AudioHubClient = robot.ensure_client(AudioHubClient.default_service_name)
audio_client.SetTimeout(3.0)
audio_client.Init()

video_client: VideoClient = robot.ensure_client(VideoClient.default_service_name)
video_client.SetTimeout(3.0)
video_client.Init()

sport_client: SportClient = robot.ensure_client(SportClient.default_service_name)
sport_client.SetTimeout(3.0)
sport_client.Init()

vui_client: VuiClient = robot.ensure_client(VuiClient.default_service_name)
vui_client.SetTimeout(3.0)
vui_client.Init()


@app.route('/', methods=['GET', 'POST'])
def dashboard():
    try:
        # scripts_directory = os.listdir(os.path.join(os.getcwd(), "go2_dashboard\scripts"))
        # sounds_directory = os.listdir(os.path.join(os.getcwd(), "go2_dashboard\sounds"))

        scripts_directory = os.listdir(os.path.join(os.getcwd(), "scripts"))
        sounds_directory = os.listdir(os.path.join(os.getcwd(), "sounds"))

        active_script = script_process['name'] if script_process['name'] else 'None'
        return render_template('index.html', scripts=scripts_directory, sounds=sounds_directory, dog_data=dog_data, active_script=active_script)
    except Exception as e:
        return str(e)

@app.route('/update_joystick', methods=['POST'])
def update_joystick():
    data = request.get_json()

    x, y, yaw = 0, 0, 0

    if data['stickId'] == 'stick1':
        x = -data['y'] * move_speed
        y = -data['x'] * move_speed
    
    if data['stickId'] == 'stick2':
        yaw = -data['x'] * turn_speed

    sport_client.Move(x, y, yaw)

    return jsonify({'status': 'success', 'data': data}), 200


def gen_frames():
    code, data = video_client.GetImageSample()

    while code == 0:
        code, data = video_client.GetImageSample()

        image_data = np.frombuffer(bytes(data), dtype=np.uint8)
        
        if image_data is None:
            continue

        frame = cv2.imdecode(image_data, cv2.IMREAD_COLOR)

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def generate_data():
    while True:
        data_array = [
            {'name': 'Voltage', 'value': dog_data['voltage']},
            {'name': 'Current', 'value': dog_data['current']},
            {'name': 'Average Temp', 'value': dog_data['avg temp']},
            {'name': 'Velocity X', 'value': dog_data['velocity x']},
            {'name': 'Velocity Y', 'value': dog_data['velocity y']},
            {'name': 'Velocity Z', 'value': dog_data['velocity z']},
            {'name': 'Yaw Speed', 'value': dog_data['yaw spd']},
        ]

        yield f"data: {json.dumps(data_array)}\n\n"
        
        time.sleep(0.1)

@app.route('/data')
def stream_data():
    return Response(generate_data(), mimetype='text/event-stream')


def audio_thread(sound_name):
    audio_client.MegaphoneEnter()
    audio_client.MegaphoneUpload(f"C:\\Users\\Saumya Varshney\\Sparky Project\\Go2DashBoard\\go2_dashboard\\sounds\\{sound_name}")
    time.sleep(10)
    audio_client.MegaphoneExit()

@app.route('/play_sound/<sound_name>')
def play_sound(sound_name):
    threading.Thread(target=audio_thread, args=[sound_name]).start()
    return redirect(url_for('dashboard'))


# Functions for extracting the content from GPT response
def extract_code(content):
    import re
    # Regular expression to find all code blocks
    regex = re.compile(r'```python\n([\s\S]*?)```')
    matches = regex.findall(content)
    
    if matches:
        all_code = "\n\n".join([match.strip() for match in matches])
        return all_code
    return ""


def extract_pre_code(content):
    import re
     # Regular expression to find and remove all `python` code blocks
    regex = re.compile(r'```python[\s\S]*?```')
    
    content_without_code = regex.sub('', content)

    if content_without_code:
        cleaned_content = content_without_code.strip()
        return cleaned_content
    return ""

# Converting Text to Audio for the robot to speak
def text_to_audio(text):
    try:
        wav_filename = "audio_response.wav"
        save_directory = 'C:\\Users\\Saumya Varshney\\Sparky Project\\Go2DashBoard\\go2_dashboard\\sounds'
        wav_filepath = os.path.join(save_directory, wav_filename)

        engine = pyttsx3.init()
        engine.save_to_file(text, wav_filepath)
        engine.runAndWait()
        
        print(f"Audio saved as: {wav_filepath}")
    except Exception as e:
        print(f"An error occurred: {e}")


chat_prompt = """You are an robot dog AI chat or voice assistant. Your name is Sparky.
All programming of you will be done with the unitree_sdk2py library.

Importing the library and creating an instance of different classes called sport_client and video_client has already been taken care.
The method definitions for each classes are defined here:

1) sport_client - Main motion control service
    Damp - sport_client.Damp() - All motor joints stop moving and enter a damping state. This mode has the highest priority and is used for emergency stops in unexpected situations
    BalanceStand - sport_client.BalanceStand() - Unlock the joint motor and switch from normal standing mode to balanced standing mode. In this mode, the attitude and height of the fuselage will always remain balanced, independent of the terrain. You can control the font and height of the body by calling the Euler() and BodyHeight() interfaces (see the corresponding section of the table for details)
    StopMove - sport_client.StopMove() - Stop the current motion and restore the internal motion parameters of Go2 to the default values
    StandUp - sport_client.StandUp() - The machine dog is standing tall normally, and the motor joint remains locked. Compared to the balanced standing mode, the posture of the robotic dog in this mode will not always maintain balance. The default standing height is 0.33m
    StandDown - sport_client.StandDown() - The robotic dog lies down and the motor joint remains locked
    RecoveryStand - sport_client.RecoveryStand() - Restore from a overturned or lying state to a balanced standing state. Whether it is overturned or not, it will return to standing
    Euler - sport_client.Euler(float roll, float pitch, float yaw) - Set the body posture angle for Go2 balance when standing or moving. The Euler angle is represented by the rotation order around the relative axis of the body and z-y-x
    Move - sport_client.Move(float vx, float vy, float vyaw) - Control movement speed. The set speed is the speed represented by the body coordinate system.
    Here is how you can set the parameters to move the Go2 in different directions:
        Move Left or Right:
        To move the Go2 to the left, you can set a negative value for the vy parameter in the velocity_move case. For example, sport_client.Move(0.3, -0.3, 0.3); will move the Go2 to the left.
        To move the Go2 to the right, you can set a positive value for the vy parameter. For example, sport_client.Move(0.3, 0.3, 0.3); will move the Go2 to the right.
        Move Forward or Backward:
        To move the Go2 forward, you can set a positive value for the vx parameter. For example, sport_client.Move(0.3, 0, 0.3); will move the Go2 forward.
        To move the Go2 backward, you can set a negative value for the vx parameter. For example, sport_client.Move(-0.3, 0, 0.3); will move the Go2 backward.
        Move in Diagonal Directions:
        To move the Go2 in diagonal directions, you can set both vx and vy parameters accordingly. For example, to move diagonally to the top right, you can use sport_client.Move(0.3, 0.3, 0.3);.
    Sit - sport_client.Sit() - Special action, robot dog sitting down. It should be noted that special actions need to be executed after the previous action is completed, otherwise it may result in abnormal actions
    RiseSit - sport_client.RiseSit() - Restore from sitting to balanced standing
    BodyHeight - sport_client.BodyHeight (float height) - Adjust the height of the body relative to the default state when standing or walking in balance. The default body height for Go2 is 0.33. For example, BodyHeight (-0.1) indicates adjusting the body height to 0.33-0.1=0.23 (m)
    SpeedLevel - sport_client.SpeedLevel (int level) - Set the speed range
    Hello - sport_client.Hello() - Say hello
    Stretch - sport_client.Stretch() - Stretch
    Wallow - sport_client.Wallow() - Rolling
    Pose - sport_client.Pose (bool flag) - Pose
    Scrape - sport_client.Scrape() - Greeting the New Year
    FrontFlip - sport_client.FrontFlip() - Front flip
    FrontJump - sport_client.FrontJump() - Jump Forward
    FrontPounce - sport_client.FrontPounce() - Move Forward
    Dance1 - sport_client.Dance1() - Dance Paragraph 1
    Dance2 - sport_client.Dance2() - Dance Paragraph 2
    GetState - sport_client.GetState (const std:: vector<std:: string>&_vector, std:: map<std:: string, std:: string>&_map) - Reference example: When the robot is in a damping state, the above example will output {"data": "damping"} results

2) video_client - Video Source Service
    GetImageSample - video_client.GetImageSample(std::vector<uint8_t>& image_sample) - Get Photos

3) vui_client - Volume Light Service
    SetVolume - vui_client.SetVolume(int level) - Sets the volume of the speaker of the robot dog to a given level
    GetVolume - vui_client.GetVolume() - Gets the volume of the speaker of the robot dog
    SetBrightness - vui_client.SetBrightness(int level) - Sets the brightness of the Headlight/Flashlight of the robot dog to a given level
    GetBrightness - vui_client.GetBrightness(int level) - Gets the brightness of the Headlight/Flashlight of the robot dog
    QuitLed - vui_client.QuitLed() - Quits the Headlight/Flashlight colr and restore to default setting
    SetLed - vui_client.SetLed(color) -  Sets the color of the Headlight/Flashlight of the robot dog. Here is the color list ('white','red','yellow','blue','green','cyan','purple')


All methods accept the appropriate arguments as specified.

There is a wait method in cases where we want to pause between commands.
It accepts a number in milliseconds:
time.sleep()
Give some delay before starting the commands.

You have to start your response in such a way that you are following the orders from your master.
Respond briefly, ensuring all information is included.
"""

messages = [{"role": "system", "content": chat_prompt}]


@app.route('/gpt_chat', methods=['POST'])
def gpt_chat():
    user_input = request.json.get("message")
    setup_logging()
    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    messages.append({"role": "user", "content": user_input})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=messages
        )
        
        bot_message = response.choices[0].message
        
        if bot_message:
            print("*************** Complete GPT Response*********************")
            print(bot_message)
            messages.append(bot_message)
            program = extract_code(bot_message["content"])
            response_msg = extract_pre_code(bot_message["content"])
            if response_msg:
                text_to_audio(response_msg)
                play_sound('audio_response.wav')
                time.sleep(2)
                # return jsonify({"message": response_msg})

            else:
                text_to_audio(bot_message["content"])
                play_sound('audio_response.wav')
                time.sleep(2)
                
            
            if program:
                print("*************** Extracted GPT Response*********************")
                print(program)
                try:
                    exec(program) 
                    time.sleep(2)
                    return jsonify({"message": response_msg})
                
                except Exception as error:
                    return jsonify({"error": f"Code execution failed: {error}"})
                
            else:
                print(response_msg)
                return jsonify({"message": response_msg})
            

        else:
            return jsonify({"error": "No response from the bot"}), 500

    except Exception as error:
        return jsonify({"error": str(error)}), 500
    

if __name__ == '__main__':
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)
