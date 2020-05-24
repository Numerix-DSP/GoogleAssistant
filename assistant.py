#!/usr/bin/env python3

# Simple Google Assistant Example
# This code requires Python >= v3.5

# This code supports two methods for interacting with Google Assistant :
# 1/ SEND_AUDIO_REQUEST  = 1
# Processed command strings are converted to audio (using gTTS) and sent to Google. The audio response is then played out
# 2/ SEND_AUDIO_REQUEST  = 0
# Processed command strings are sent to Google (using assistant_textinput.py). The text response is then converted to audio (using gTTS) and played out

import re
import sys
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import pyaudio
from six.moves import queue
import shlex
import subprocess
import time
from time import strftime
from gtts import gTTS
import datetime
from subprocess import Popen, PIPE

# Audio recording parameters
RATE                = 48000
CHUNK               = int(RATE / 10)        # 100ms
AUDIO_DEVICE_ID     = "numid=2"
INITIAL_VOLUME      = 200
FORMAT              = pyaudio.paInt16
DEVICE              = -1                    # Default audio device
SEND_AUDIO_REQUEST  = 0                     # Set to ''1 to send audio request, '0' to send text request


key_phrases = ['smart assistant','ok smart assistant','hey smart assistant',
            'ok assistant','hey assistant', 'ok google','hey google'
            'exit','quit',
            'play music', 'stop music', 'stop the music', 'stop audio',
            'lower volume','reduce volume','decrease volume','volume down',
            'increase volume','volume up',
            'mute, mute audio',
            'unmute, unmute audio',
            'maximum volume','max volume','volume maximum','volume max',
            'minimum volume','min volume','volume minimum','volume min',
            'volume half','half volume',
            'what\'s the time','what time is it','what is the time',
            'what\'s the date','what date is it','what is the date']

class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=FORMAT,
             # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            input_device_index=DEVICE,
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)

def process_command(cmdstr):
    if (SEND_AUDIO_REQUEST):    # Send audio request to Google
        tts = gTTS(cmdstr)
        tts.save('assist-tmp.mp3')
        print ("Creating audio request")
        subprocess.Popen(shlex.split("sox assist-tmp.mp3 -r 16000 assist-tmp1.wav"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#        subprocess.Popen(shlex.split("aplay assist-tmp1.wav"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print ("Sending audio request")
        subprocess.Popen(shlex.split("googlesamples-assistant-pushtotalk -i assist-tmp1.wav"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    else:                       # Send text request to Google
#        print ("Sending text request :", cmdstr)
        gcmdstr = "python3 /home/pi/.local/lib/python3.7/site-packages/googlesamples/assistant/grpc/assistant_textinput.py --request \"" + cmdstr + "\""
        pipe = subprocess.Popen(shlex.split(gcmdstr), stdout=PIPE, stderr=subprocess.DEVNULL)
        grespstr = str(pipe.communicate()[0])
        if grespstr.strip():                        # Check if there is a response, after removing white space
#            print ("Google response :", grespstr)
            if "<@assistant>" in grespstr:          # Check for valid Google assistant response
                grespstr = grespstr.split("<@assistant>", 1)[1]     # Clean up text
                if "http" in grespstr:
                    grespstr = grespstr.split("http", 1)[0]
                if "\\n" in grespstr:
                    grespstr = grespstr.replace("\\n", ". ")
                if "\n" in grespstr:
                    grespstr = grespstr.replace("\n", ". ")
                if "\"" in grespstr:
                    grespstr = grespstr.replace("\"", " ")
                if "\\" in grespstr:
                    grespstr = grespstr.replace("\\", " ")
                if "(" in grespstr:
                    grespstr = grespstr.replace("(", "")
                if ")" in grespstr:
                    grespstr = grespstr.replace(")", "")
                if "Wikipedia" in grespstr:
                    grespstr = grespstr.replace("Wikipedia", "")
    #            print ("Processed Google response :", grespstr)
                if grespstr.strip():                      # Check if there is any text left after clean up
                    tts = gTTS(grespstr)
                    tts.save('assist-tmp.mp3')
                    subprocess.Popen(shlex.split("mpg321 assist-tmp.mp3"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def listen_print_loop(responses):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """

    smart_assistant_flag = 0            # Indicate if smart assistant request initiated

    volume = INITIAL_VOLUME
    prevVolume = INITIAL_VOLUME

    num_chars_printed = 0
    print ("\n\n\nWaiting for your input. Say \"exit\" or \"quit\" to quit the program ...");
    print ("\nPlay Music, Increase Volume, Decrease Volume, Mute, Unmute, Volume half, Maximum Volume");
    print ("What time is it, What date is it");
    print ("smart assistant ..., ok assistant ..., ok google ..., hey google, ...\n")

    for response in responses:
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
            sys.stdout.write(transcript + overwrite_chars + '\r')
            sys.stdout.flush()

            num_chars_printed = len(transcript)


        else:
            # Check to see if any of the alternatives match the key phrases list
            # Otherwise use existing result.alternatives[0].transcript
            num_alternatives = len(result.alternatives)
            print("Num alternatives = ", str(num_alternatives))
            for i in range(num_alternatives):
#                print("alternative[", str(i), "] = ", result.alternatives[i].transcript)
                if (result.alternatives[i].transcript in key_phrases):
                    transcript = result.alternatives[i].transcript
                    continue

            print("transcript :", transcript)

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r'\b(exit|quit)\b', transcript.lower(), re.I):
                print('Exiting..')
                subprocess.Popen(shlex.split("killall -9 mpg321"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break

            if re.search(r'\b(play music)\b', transcript.lower(), re.I):
                print('Playing Music..')
                subprocess.Popen(shlex.split("killall -9 mpg321"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.Popen(shlex.split("mpg321 --list songlist.lst -Z --loop 0"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(stop music|stop the music|stop audio)\b', transcript.lower(), re.I):
                print('Stopping Music..')
                subprocess.Popen(shlex.split("killall -9 mpg321"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(increase volume|volume up)\b', transcript.lower(), re.I):
                print('Increasing volume..')
                volume += 25
                if volume > 255:
                    volume = 255
                subprocess.run(["amixer", "cset", AUDIO_DEVICE_ID, str(volume)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(lower volume|reduce volume|decrease volume|volume down)\b', transcript.lower(), re.I):
                print('Reducing volume..')
                volume -= 25
                if volume < 0:
                    volume = 0
                subprocess.run(["amixer", "cset", AUDIO_DEVICE_ID, str(volume)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(mute|mute audio)\b', transcript.lower(), re.I):
                print('Muting audio..')
                prevVolume = volume
                volume = 0
                subprocess.run(["amixer", "cset", AUDIO_DEVICE_ID, str(volume)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(unmute|unmute audio)\b', transcript.lower(), re.I):
                print('Unuting audio..')
                volume = prevVolume
                subprocess.run(["amixer", "cset", AUDIO_DEVICE_ID, str(volume)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(maximum volume|max volume|volume maximum|volume max)\b', transcript.lower(), re.I):
                print('Maximum volume..')
                volume = 255
                subprocess.run(["amixer", "cset", AUDIO_DEVICE_ID, str(volume)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(minimum volume|min volume|volume minimum|volume min)\b', transcript.lower(), re.I):
                print('Maximum volume..')
                volume = 25
                subprocess.run(["amixer", "cset", AUDIO_DEVICE_ID, str(volume)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(medium volume|volume medium)\b', transcript.lower(), re.I):
                print('Medimum volume..')
                volume = 200
                subprocess.run(["amixer", "cset", AUDIO_DEVICE_ID, str(volume)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(volume half|half volume)\b', transcript.lower(), re.I):
                print('Volume 50%..')
                volume = 127
                subprocess.run(["amixer", "cset", AUDIO_DEVICE_ID, str(volume)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(what\'s the time|what time is it|what is the time)\b', transcript.lower(), re.I):
                print('Time..')
                tts = gTTS('The time is ' + str(strftime("%H")) + " " + str(strftime("%M")))
                tts.save('assist-tmp.mp3')
                subprocess.Popen(["mpg321", "assist-tmp.mp3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if re.search(r'\b(what\'s the date|what date is it|what is the date)\b', transcript.lower(), re.I):
                print('Date..')
                tts = gTTS('The date is ' + str(datetime.datetime.now().date()))
                tts.save('assist-tmp.mp3')
                subprocess.Popen(["mpg321", "assist-tmp.mp3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if smart_assistant_flag:                    # Handle smart assistant follow up - if there is one
                print('smart assistant request..')
                cmdstr = transcript.lower()
                if cmdstr.strip():                      # Check if there is a command, after removing 'keyword'
                    process_command(cmdstr)
                    smart_assistant_flag = 0            # Smart assistant request handled

            if re.search(r'\b(smart assistant|hey smart assistant|ok smart assistant|ok assistant|hey assistant|hey google|ok google)\b', transcript.lower(), re.I):
                # We'll grab the text request, remove the 'keyword', convert to audio and send to Google as a .wav
                print('smart assistant..')
                cmdstr = transcript.lower()
                cmdstr = cmdstr.replace("ok smart assistant","")    # Remove any key phrases
                cmdstr = cmdstr.replace("hey smart assistant","")
                cmdstr = cmdstr.replace("ok assistant","")
                cmdstr = cmdstr.replace("hey assistant","")
                cmdstr = cmdstr.replace("smart assistant","")
                cmdstr = cmdstr.replace("ok google","")
                cmdstr = cmdstr.replace("hey google","")
                print("cmdstr:" + cmdstr)
                if cmdstr.strip():                      # Check if there is a command, after removing key phrases
                    process_command(cmdstr)
                    smart_assistant_flag = 0            # Smart assistant request handled
                else:
                    smart_assistant_flag = 1            # Smart assistant request needs to be handled

                print ("Smart Assistant done ...")


            num_chars_printed = 0
            transcript = ""


def main():
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    language_code = 'en-GB'  # a BCP-47 language tag

                                        # Prepare audio
    subprocess.Popen(shlex.split("killall -9 mpg321"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["amixer", "cset", AUDIO_DEVICE_ID, str(INITIAL_VOLUME)])

    client = speech.SpeechClient()
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        model="command_and_search",
        language_code=language_code,
        max_alternatives=10,
        profanity_filter=True,
        speech_contexts = [{'phrases':key_phrases}]
        )
    streaming_config = types.StreamingRecognitionConfig(
        config=config,
        interim_results=True)

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (types.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

        responses = client.streaming_recognize(streaming_config, requests)

        # Now, put the transcription responses to use.
        listen_print_loop(responses)


if __name__ == '__main__':
    main()

