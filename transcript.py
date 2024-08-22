import streamlit as st
import azure.cognitiveservices.speech as speechsdk
import re
import spacy
import tempfile
import os

def download_spacy_model():
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        st.write("Downloading SpaCy model...")
        from spacy.cli import download
        download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
    return nlp

# Load the SpaCy model
nlp = download_spacy_model()

# Function to redact sensitive information in a single segment
def redact_segment(segment):
    segment = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE]', segment)
    segment = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', segment)
    segment = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[EMAIL]', segment)
    segment = re.sub(r'\d+', '[NUMBER]', segment)
    
    doc = nlp(segment)
    for ent in doc.ents:
        if ent.label_ in ["PERSON", "GPE", "ORG", "DATE"]:
            segment = segment.replace(ent.text, '[REDACTED]')
    
    return segment

# Function to transcribe the audio with real-time diarization
def transcribe_with_diarization(file_path):
    speech_key = st.secrets["speech_key"]
    speech_region = "eastus"
    
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    speech_config.speech_recognition_language = "en-US"

    transcript = []
    
    done = False

    def transcribed_callback(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            transcript.append((evt.result.text, evt.result.speaker_id))
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print("No speech could be recognized: {}".format(evt.result.no_match_details))

    def session_stopped(evt):
        nonlocal done
        done = True
        print("Session stopped.")

    audio_config = speechsdk.audio.AudioConfig(filename=file_path)
    transcriber = speechsdk.transcription.ConversationTranscriber(speech_config, audio_config)
    transcriber.transcribed.connect(transcribed_callback)
    transcriber.session_stopped.connect(session_stopped)

    transcriber.start_transcribing_async().get()

    # Wait until the session is stopped
    while not done:
        continue

    transcriber.stop_transcribing_async().get()
    
    return transcript

# Streamlit UI
st.title("Audio Transcription, Diarization, and Redaction")
st.write("Upload a WAV file to transcribe, diarize, and redact sensitive information.")

uploaded_file = st.file_uploader("Choose a WAV file", type="wav")

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        temp_file.write(uploaded_file.read())
        temp_file_path = temp_file.name

    st.write("Transcribing the audio with speaker diarization...")
    transcript = transcribe_with_diarization(temp_file_path)
    
    st.write("**Original Transcription with Speaker IDs:**")
    if transcript:
        for segment, speaker_id in transcript:
            st.write(f"Speaker {speaker_id}: {segment}")
        
        # Redacting each segment while preserving speaker IDs
        st.write("**Redacted Transcription with Speaker IDs:**")
        for segment, speaker_id in transcript:
            redacted_segment = redact_segment(segment)
            st.write(f"Speaker {speaker_id}: {redacted_segment}")
    else:
        st.write("No transcription could be processed.")

