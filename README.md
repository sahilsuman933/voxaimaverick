# Real-Time Voice Chat AI Assistant

A FastAPI-based application that enables real-time voice conversations with an AI assistant using WebRTC, Deepgram for speech recognition, and Cartesia for text-to-speech synthesis.

## Features

- Real-time speech-to-text using Deepgram
- Natural language processing with OpenAI GPT-4
- Text-to-speech synthesis with Cartesia
- WebSocket-based communication
- Twilio integration for voice calls

## Prerequisites

- Python 3.8+
- FastAPI
- OpenAI API key
- Deepgram API key
- Cartesia API key
- Twilio account (for voice calls)

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
OPENAI_API_KEY=your_openai_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
CARTERSIA_API_KEY=your_cartesia_api_key
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
```

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Start the FastAPI server:
```bash
fastapi run dev
```

2. Configure your Twilio webhook to point to your `/twilio` endpoint

3. The application will:
   - Convert incoming audio to text using Deepgram
   - Process the text using GPT-4
   - Convert responses to speech using Cartesia
   - Stream the audio response back to the caller

## API Endpoints

- `POST /twilio`: Handles incoming Twilio voice calls
- `WebSocket /ws`: Manages real-time audio streaming and processing
