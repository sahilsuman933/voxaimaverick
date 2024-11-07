from fastapi import FastAPI, WebSocket, Response
import websockets
import base64
import json
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = FastAPI()


classifier_statement = """Determine if the user's statement ends with a complete thought and you should respond.
The user text is transcribed speech. You are trying to determine if:
1. the user has finished talking and expects a response from you, or
2. this statement is incomplete and the user will continue talking
A previous assistant response is provided for additional context. But you are only evaluating the user text. 
The user text may contain multiple fragments concatentated together. There may be repeated words or mistakes in the transcription. There may be grammatical errors. There may be extra punctuation. Ignore all of that. Interpret the transcribed text as text that would have been spoken. Then consider only whether the user has finished speaking and is expecting a response.
Categorize the last user statement as either complete with the user now expecting a response, or incomplete.
Return 'YES' if text is likely complete and the user is expecting a response. Return 'NO' if the text seems to be a partial expression or unfinished thought.
If you are not sure, respond with your best guess. If the user is expecting a response, respond with YES. If the user is not expecting a response, respond with NO. Always output either YES or NO and no other text.
Respond only YES or NO
Examples:
User: What's the capital of
Assistant: NO
User: What's the captial of France?
Assistant: YES
User: Tell me a story about
Assistant: NO
User: Tell me a story about a dragon
Assistant YES
User: Is there a
Assistant: NO
User: Is there a large
Assistant: NO
User: Is there a large lake near Chicago?
Assistant: YES
User: When is the longest day of the year?
Assistant: YES
User: When when is the longest day of the year
Assistant: YES
User: When when is the
ASSISTANT: NO
User: What is the um I u
Assistant: NO
User: What is the um i u largest city in the world
Assistant: YES
User: How much does a how much does an adult elephant weigh?
Assistant: YES
User: How much does a how much does
Assistant: NO
User: What can you tell me All the
Assistant: NO
User: What can you tell me All the prime numbers less than 100
Assistant: YES
User: What's the what's the length of the Amazon River?
Assistant: YES
User: What's what's the length of the Amazon River?
Assistant: YES
User: What's what's the length of the Amazon River
Assistant: YES
User: What's what's the best way to get a coffee stain out of a white shirt
Assistant: YES
"""

messages = [
    {"role": "system", "content": "You are a helpful LLM in a WebRTC call. Your goal is to demonstrate your capabilities in a succinct way. Your output will be converted to audio so don't include special characters in your answers. Respond to what the user said in a creative and helpful way. Please be very concise in your responses. Unless you are explicitly asked to do otherwise, give me the shortest complete answer possible without unnecessary elaboration. Generally you should answer with a single sentence."}
]

@app.post("/twilio")
async def twilio_call():
    data = '<?xml version="1.0" encoding="UTF-8"?> <Response> <Connect> <Stream url="wss://engaged-guppy-engaging.ngrok-free.app/ws" /> </Connect> <Pause length="40"/> </Response>'
    return Response(content=data, media_type="application/xml")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        deepgram_ws = await websockets.connect(
            'wss://api.deepgram.com/v1/listen?encoding=mulaw&sample_rate=8000&channels=1&model=nova-2&endpointing=20&interim_results=true&language=en-IN',
            extra_headers={'Authorization': f'Token {os.getenv("DEEPGRAM_API_KEY")}'},
            ping_interval=5,
            ping_timeout=20
        )
        
        cartesia_ws = await websockets.connect(f"wss://api.cartesia.ai/tts/websocket?api_key={os.getenv('CARTESIA_API_KEY')}&cartesia_version=2024-06-10")
        
        async def send_audio():
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)
                if data["event"] == "media":
                    decoded_chunk = base64.b64decode(data['media']['payload'])
                    try:
                        await deepgram_ws.send(decoded_chunk)
                    except Exception as e:
                        print(f"Error sending audio data: {e}")
                elif data["event"] == "connected":
                    pass
                elif data["event"] == "start":
                    global streamsid
                    streamsid = data["start"]["streamSid"]
                    print("Call started.")
                elif data["event"] == "stop":
                    print("Call ended.")
                    break

        async def receive_transcripts():
            try:
                async for message in deepgram_ws:
                    message = json.loads(message)
                    if message['type'] == 'Results':
                        transcript = message['channel']['alternatives'][0]['transcript']
                        if transcript == '': 
                            continue

                        if message['is_final']:
                            print(f"[Transcriber]: Final Transcript - {transcript}")
                            messages.append({"role": "user", "content": transcript})
                            
                            classifier_completion = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[{"role": "system", "content": classifier_statement}, {"role": "user", "content": f'Assistant: {messages[-1]["content"]}\n User: {transcript}'}],
                                stream=True,
                                max_tokens=50,
                                temperature=0.3
                            )

                            classifier_output = ""
                            for chunk in classifier_completion:
                                if chunk.choices[0].finish_reason is None:
                                    if chunk.choices[0].delta.content is not None:
                                        classifier_output += chunk.choices[0].delta.content

                            print("[Classifier]: Speak - ", classifier_output)
                            if classifier_output == "YES":
                                completion = client.chat.completions.create(
                                    model="gpt-4o",
                                    messages=messages,
                                    stream=True,
                                    max_tokens=50,
                                    temperature=0.3
                                )

                                model_output = ""  # Initialize model_output before the loop
                                for chunk in completion:
                                    if chunk.choices[0].finish_reason is None:
                                        if chunk.choices[0].delta.content is not None:  # Check if content exists
                                            model_output += chunk.choices[0].delta.content
                                    else:
                                        print("[LLM Output]: ", model_output)
                                        messages.append({"role": "assistant", "content": model_output})
                                        await cartesia_ws.send(json.dumps({
                                            "model_id": "sonic-english",
                                            "transcript": model_output,
                                            "voice": {
                                                "mode": "id",
                                                "id": "7ed36e3c-280f-4862-badb-d1b8ec65bddd"
                                            },
                                            "language": "en",
                                            "context_id": "happy-monkeys-fly",
                                            "output_format": {
                                                "container": "raw",
                                                "encoding": "pcm_mulaw",
                                                "sample_rate": 8000
                                            },
                                            "add_timestamps": True,
                                            "continue": True
                                        }))
                                        
                                        model_output = ""

                        else:
                            print(f"[Transcriber]: Partial Transcript - {transcript}")

                    else:
                        print(message)
            except Exception as e:
                print(f"Error receiving transcript: {e}")

        async def tts_output():
            try:
                async for message in cartesia_ws:
                    if json.loads(message)['type'] == 'chunk':
                        payload_data = {
                            'event': 'media',
                            'streamSid': streamsid,
                            'media': {
                                'payload': json.loads(message)['data']
                            }
                        }
                        # Convert the JSON to a string and then encode it to bytes before sending
                        await websocket.send_text(json.dumps(payload_data))

            except Exception as e:
                print(f"Error receiving TTS output: {e}")

        # Run send_audio and receive_transcripts concurrently
        await asyncio.gather(send_audio(), receive_transcripts(), tts_output())

    except websockets.exceptions.ConnectionClosed:
        print("Deepgram connection closed")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if deepgram_ws and not deepgram_ws.closed:
            await deepgram_ws.close()


