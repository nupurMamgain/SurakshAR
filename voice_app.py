"""
voice_app.py

WHAT THIS FILE DOES (in simple words):
This is the VOICE version of the bot. It uses the exact same "brain"
from app.py (the RAG chain, the rules, the refusal logic) but instead of
typing, you SPEAK your question, and instead of reading, the bot SPEAKS
its answer back to you.

Two new abilities added here:
- LISTEN: turns your microphone speech into text (Speech-to-Text / STT)
- SPEAK: turns the bot's text reply into audio you can hear (Text-to-
  Speech / TTS)

Setup (in addition to app.py's setup):
    pip install -r requirements.txt

    On Windows, if installing PyAudio fails, run this instead:
        pip install pipwin
        pipwin install pyaudio

Run:
    python voice_app.py

Say "quit" or "exit" out loud (or press Ctrl+C) to stop.
"""

import os
import tempfile
import speech_recognition as sr
from gtts import gTTS
from playsound import playsound

# We reuse everything from app.py instead of rewriting it, so both the
# typed version and the voice version always behave the same way.
from app import (
    build_or_load_vectorstore,
    build_chain,
    handle_message,
    detect_language,
)

# This is the tool that "listens" through your microphone.
recognizer = sr.Recognizer()


# ===========================================================================
# LISTEN: turn microphone speech into text
# ===========================================================================
def listen() -> str:
    # "with sr.Microphone()" turns your mic on for a moment, then turns
    # it back off automatically when done - so it's not always recording.
    with sr.Microphone() as source:
        print("Listening... speak now.")
        # This lets the tool "learn" what silence/background noise sounds
        # like for half a second, so it can tell speech apart from noise.
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        # This actually records what you say (waits up to 8 seconds for
        # you to start talking, then records up to 15 seconds total).
        audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)

    print("Recognizing...")
    # We try Hindi first, then English, and use whichever one actually
    # understands something - so the worker doesn't need to pick a mode.
    for lang_code in ("hi-IN", "en-IN"):
        try:
            text = recognizer.recognize_google(audio, language=lang_code)
            if text.strip():
                return text
        except sr.UnknownValueError:
            # Google's engine didn't understand any words in this
            # language - just try the next language.
            continue
        except sr.RequestError as e:
            # This means there was a problem reaching Google's servers
            # (usually an internet issue).
            print(f"Speech recognition service error: {e}")
            return ""
    return ""  # nothing was understood in either language


# ===========================================================================
# SPEAK: turn the bot's text reply into audio and play it out loud
# ===========================================================================
def speak(text: str, lang: str):
    # gTTS needs a short language code: "hi" for Hindi, "en" for English.
    tts_lang = "hi" if lang == "hi" else "en"

    # We create a temporary audio file, play it, then delete it - so we
    # don't fill up your computer with leftover sound files.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        tmp_path = tmp_file.name
    try:
        gTTS(text=text, lang=tts_lang).save(tmp_path)
        playsound(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass  # if it's already gone, that's fine


# ===========================================================================
# MAIN VOICE LOOP: listen -> think -> speak, again and again
# ===========================================================================
def main():
    print("Building/loading knowledge base...")
    vectorstore = build_or_load_vectorstore()
    chain, retriever = build_chain(vectorstore)
    print("Suraksha Sathi (voice mode) is ready. Say 'quit' to exit.\n")

    while True:
        try:
            user_text = listen()
        except sr.WaitTimeoutError:
            print("Didn't hear anything, try again.\n")
            continue

        if not user_text:
            print("Sorry, I didn't catch that. Please try again.\n")
            continue

        print(f"You said: {user_text}")

        # Let the worker say "quit" or "exit" out loud to stop the app.
        if user_text.strip().lower() in {"quit", "exit", "बंद करो"}:
            break

        # This is the exact same brain used by the typed version.
        reply = handle_message(user_text, chain, retriever)
        print(f"Suraksha Sathi: {reply}\n")

        # Speak the reply out loud, in whichever language it was written in.
        reply_lang = detect_language(reply)
        speak(reply, reply_lang)


if __name__ == "__main__":
    main()
