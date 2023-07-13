import argparse
import queue
import sys
import sounddevice as sd
import pyttsx3
import openai
from vosk import Model, KaldiRecognizer

q = queue.Queue()
engine = pyttsx3.init()

openai.api_key = "Your API Key"
context="Tu es un robot assistant dans un laboratoire. Ton nom est Bagley et tu peux faire preuve de cynisme dans certaines de tes réponses. Tu m'appelles Humain. Tes réponses doivent être brèves et données dans un format adapté à la synthèse vocale."

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text

def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument(
    "-l", "--list-devices", action="store_true",
    help="show list of audio devices and exit")
args, remaining = parser.parse_known_args()
if args.list_devices:
    print(sd.query_devices())
    parser.exit(0)
parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    parents=[parser])
parser.add_argument(
    "-f", "--filename", type=str, metavar="FILENAME",
    help="audio file to store recording to")
parser.add_argument(
    "-d", "--device", type=int_or_str,
    help="input device (numeric ID or substring)")
parser.add_argument(
    "-r", "--samplerate", type=int, help="sampling rate")
parser.add_argument(
    "-m", "--model", type=str, help="language model; e.g. en-us, fr, nl; default is en-us")
args = parser.parse_args(remaining)

try:
    if args.samplerate is None:
        device_info = sd.query_devices(args.device, "input")
        # soundfile expects an int, sounddevice provides a float:
        args.samplerate = int(device_info["default_samplerate"])
        
    if args.model is None:
        model = Model(lang="fr")
    else:
        model = Model(lang=args.model)

    if args.filename:
        dump_fn = open(args.filename, "wb")
    else:
        dump_fn = None

    with sd.RawInputStream(samplerate=args.samplerate, blocksize = 8000, device=args.device,
            dtype="int16", channels=1, callback=callback):
        print("\n"+"#"*60)
        print("Press Ctrl+C to stop the recording")
        print("#"*60+"\n")

        rec = KaldiRecognizer(model, args.samplerate)
        while True:
            #=========================================STT
            data = q.get()
            if rec.AcceptWaveform(data):
                result = rec.Result()[14:-3]

                if result !="":
                    q.task_done()  # Ajoutez cette ligne pour suspendre temporairement q.get()
                    print("Detected : "+result)
                    #=========================================OpenAI API
                    response=openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                            {"role": "system","content": context},
                            {"role": "user", "content": result},
                        ],
                    )

                    #=========================================TTS
                    engine.say(response['choices'][0]['message']['content'])
                    engine.runAndWait()

                    print("Response : "+str(response['choices'][0]['message']['content']))
                    q = queue.Queue()  # Ajoutez cette ligne pour reprendre q.get()

            if dump_fn is not None:
                dump_fn.write(data)

except KeyboardInterrupt:
    print("\nDone")
    parser.exit(0)
except Exception as e:
    parser.exit(type(e).__name__ + ": " + str(e))
