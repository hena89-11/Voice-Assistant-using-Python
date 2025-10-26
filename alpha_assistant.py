#!/usr/bin/env python3
"""
alpha_assistant.py

A corrected and improved voice assistant based on the user's uploaded Munna.txt.
Features:
 - Text-to-speech and speech recognition with graceful fallback to text input.
 - Time/date reporting.
 - Jokes via pyjokes.
 - Wikipedia summary lookup.
 - Play YouTube songs via pywhatkit.
 - Take screenshots and save them to a sensible folder.
 - Send email using SMTP with credentials taken from environment variables.
 - CPU and battery reporting via psutil.
 - Clean command parsing loop with safe exits.

Security:
 - No hard-coded credentials. Uses environment variables EMAIL_USER and EMAIL_PASS,
   and optionally a .env file (use `python-dotenv` to load).
"""

import os
import sys
import datetime
import logging
import smtplib
import webbrowser
from pathlib import Path
from typing import Optional

# Third-party imports (listed in requirements.txt)
try:
    import pyttsx3
    import speech_recognition as sr
    import pyjokes
    import wikipedia
    import pywhatkit
    import psutil
    import pyautogui
except Exception as e:
    print("One or more required packages are missing. Install from requirements.txt.")
    raise

# Optional: load environment variables from a .env file if python-dotenv is installed.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional. Environment variables can be set directly in the OS.
    pass

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Initialize TTS engine once
_engine = pyttsx3.init()
# Optionally configure voice rate / volume:
try:
    _engine.setProperty('rate', 150)
except Exception:
    pass


def speak(text: str) -> None:
    """
    Speak the provided text using pyttsx3 and also print it to stdout.
    """
    if not text:
        return
    print("Alpha:", text)
    try:
        _engine.say(str(text))
        _engine.runAndWait()
    except Exception as ex:
        logging.warning("TTS failed, proceeding without sound: %s", ex)


def get_time() -> str:
    return datetime.datetime.now().strftime("%I:%M:%S %p")


def get_date() -> str:
    now = datetime.datetime.now()
    return now.strftime("%A, %d %B %Y")


def tell_time() -> None:
    speak(f"The current time is {get_time()}")


def tell_date() -> None:
    speak(f"Today is {get_date()}")


def tell_joke() -> None:
    try:
        joke = pyjokes.get_joke()
        speak(joke)
    except Exception as e:
        speak("Sorry, I could not fetch a joke.")
        logging.exception(e)


def wishme() -> None:
    """
    Greet the user based on hour of day and announce time/date.
    """
    hour = datetime.datetime.now().hour
    if 6 <= hour < 12:
        speak("Good morning.")
    elif 12 <= hour < 18:
        speak("Good afternoon.")
    elif 18 <= hour < 24:
        speak("Good evening.")
    else:
        speak("Good night.")
    speak("Welcome back. Alpha is at your service.")
    tell_time()
    tell_date()


def cpu_status() -> None:
    try:
        usage = psutil.cpu_percent(interval=1)
        battery = psutil.sensors_battery()
        speak(f"CPU usage is at {usage} percent.")
        if battery is not None:
            speak(f"Battery is at {battery.percent} percent.")
        else:
            speak("Battery information is not available on this system.")
    except Exception as e:
        logging.exception("Failed to get CPU/battery status: %s", e)
        speak("Unable to retrieve CPU or battery status.")


def take_command(timeout: int = 5, phrase_time_limit: Optional[int] = 8) -> str:
    """
    Listen using the microphone and return recognized text.
    Falls back to a text input prompt if recognition fails.
    """
    r = sr.Recognizer()
    with sr.Microphone() as source:
        speak("Listening...")
        r.pause_threshold = 0.6
        try:
            audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            speak("No speech detected within the timeout. Please type your command.")
            return input("Type command: ").strip().lower()

    try:
        speak("Recognizing...")
        query = r.recognize_google(audio, language="en-IN")
        logging.info("Recognized query: %s", query)
        return query.lower()
    except sr.UnknownValueError:
        speak("Sorry, I did not understand. Please type your command.")
        return input("Type command: ").strip().lower()
    except sr.RequestError as e:
        logging.exception("Speech recognition request failed: %s", e)
        speak("Speech recognition service failed. Please type your command.")
        return input("Type command: ").strip().lower()
    except Exception as e:
        logging.exception("Unexpected error in take_command: %s", e)
        return input("Type command: ").strip().lower()


def send_email(to_address: str, subject: str, body: str) -> bool:
    """
    Send an email using SMTP. Credentials are read from environment variables:
    EMAIL_USER and EMAIL_PASS. For Gmail, use an app password and 2FA; do NOT
    use your main password.
    """
    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASS")  # App password or SMTP password

    if not email_user or not email_pass:
        speak("Email credentials are not configured. Please set EMAIL_USER and EMAIL_PASS environment variables.")
        logging.error("Missing EMAIL_USER or EMAIL_PASS environment variables.")
        return False

    message = f"From: {email_user}\nTo: {to_address}\nSubject: {subject}\n\n{body}"
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=20)
        server.ehlo()
        server.starttls()
        server.login(email_user, email_pass)
        server.sendmail(email_user, to_address, message)
        server.quit()
        speak("Email sent successfully.")
        return True
    except Exception as e:
        logging.exception("Failed to send email: %s", e)
        speak("Failed to send the email. Check the log for details.")
        return False


def take_screenshot(save_dir: Optional[str] = None) -> Optional[Path]:
    """
    Take a screenshot and save to user's Pictures/Screenshots or specified directory.
    Returns Path to saved file, or None if failed.
    """
    try:
        if save_dir is None:
            home = Path.home()
            # Create a Screenshots folder under Pictures if possible
            pictures = home / "Pictures"
            save_dir_path = pictures / "Screenshots"
        else:
            save_dir_path = Path(save_dir).expanduser()

        save_dir_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = save_dir_path / f"screenshot_{timestamp}.png"
        img = pyautogui.screenshot()
        img.save(str(filename))
        speak(f"Screenshot saved to {filename}")
        return filename
    except Exception as e:
        logging.exception("Screenshot failed: %s", e)
        speak("Unable to take screenshot.")
        return None


def search_in_chrome(query: str) -> None:
    """
    Open a search for `query` in the default browser.
    Uses webbrowser module which is cross-platform.
    """
    if not query:
        speak("No search query provided.")
        return
    speak(f"Searching for {query}")
    try:
        # Use the user's default browser
        webbrowser.open_new_tab(f"https://www.google.com/search?q={query}")
    except Exception as e:
        logging.exception("Failed to open web browser: %s", e)
        speak("Unable to open the web browser.")


def wiki_lookup(term: str, sentences: int = 1) -> None:
    if not term:
        speak("No search term provided for Wikipedia.")
        return
    try:
        speak(f"Searching Wikipedia for {term}")
        summary = wikipedia.summary(term, sentences=sentences)
        speak(summary)
    except wikipedia.exceptions.DisambiguationError as e:
        logging.exception("Wikipedia disambiguation: %s", e)
        speak("The term is ambiguous. Please be more specific.")
    except wikipedia.exceptions.PageError:
        speak("No Wikipedia page found for that term.")
    except Exception as e:
        logging.exception("Wikipedia lookup failed: %s", e)
        speak("An error occurred while searching Wikipedia.")


def play_song(song_name: str) -> None:
    if not song_name:
        speak("No song specified.")
        return
    speak(f"Playing {song_name} on YouTube.")
    try:
        pywhatkit.playonyt(song_name)
    except Exception as e:
        logging.exception("Failed to play song: %s", e)
        speak("Unable to play the song.")


def remember_to_file(note: str, filename: str = "data.txt") -> None:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(note)
        speak("I will remember that.")
    except Exception as e:
        logging.exception("Failed to write remember file: %s", e)
        speak("Unable to save the note.")


def read_memory(filename: str = "data.txt") -> None:
    try:
        if not Path(filename).exists():
            speak("I have nothing saved yet.")
            return
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            speak("You asked me to remember the following:")
            speak(content)
        else:
            speak("The memory file is empty.")
    except Exception as e:
        logging.exception("Failed to read memory file: %s", e)
        speak("Unable to read the memory file.")


def parse_and_execute(query: str) -> bool:
    """
    Parse the user's query and execute commands.
    Returns True to continue the main loop, False to exit.
    """
    if not query:
        return True

    # Control commands
    if any(w in query for w in ("exit", "quit", "bye", "goodbye")):
        speak("Goodbye. Have a nice day.")
        return False

    # Time and date
    if "time" in query:
        tell_time()
        return True
    if "date" in query:
        tell_date()
        return True

    # Greetings / meta
    if "your name" in query or "what is your name" in query:
        speak("My name is Alpha.")
        return True
    if "how can you help" in query or "how can you help me" in query:
        speak("I can tell time, take screenshots, send email, search the web, play songs and more.")
        return True

    # Wikipedia
    if "wikipedia" in query:
        term = query.replace("wikipedia", "").strip()
        if not term:
            # ask for term
            speak("What would you like me to search on Wikipedia?")
            term = take_command()
        wiki_lookup(term, sentences=2)
        return True

    # Search web
    if "search" in query or "search in chrome" in query or "google" in query:
        # strip trigger words
        to_search = query.replace("search in chrome", "").replace("search", "").replace("google", "").strip()
        if not to_search:
            speak("What should I search for?")
            to_search = take_command()
        search_in_chrome(to_search)
        return True

    # Email
    if "send email" in query or "email" in query:
        speak("What should be the subject?")
        subject = take_command()
        speak("What should I say in the email?")
        body = take_command()
        if "@" in subject and "." in subject and " " not in subject:
            # If user accidentally put the email address in subject, assume they mean recipient
            to_addr = subject
            subject = "No subject"
        else:
            speak("Who should I send it to? Please type the email address.")
            to_addr = input("Recipient email: ").strip()
        send_email(to_addr, subject, body)
        return True

    # Screenshot
    if "screenshot" in query or "screen shot" in query:
        take_screenshot()
        return True

    # CPU status
    if "cpu" in query or "battery" in query:
        cpu_status()
        return True

    # Remember/read memory
    if "remember that" in query or "remember" in query:
        speak("What should I remember?")
        note = take_command()
        remember_to_file(note)
        return True
    if "do you know anything" in query or "what do you remember" in query or "what did i tell you" in query:
        read_memory()
        return True

    # Play song
    if "play" in query or "play song" in query:
        # attempt to extract the song name
        song = query.replace("play", "").replace("play song", "").strip()
        if not song:
            speak("Which song should I play?")
            song = take_command()
        play_song(song)
        return True

    # Joke
    if "joke" in query:
        tell_joke()
        return True

    # Fallback: open a web search
    speak("I did not understand exactly. I will search the web for you.")
    search_in_chrome(query)
    return True


def main() -> None:
    """
    Main entrypoint.
    """
    speak("Starting Alpha Assistant.")
    wishme()
    try:
        keep_running = True
        while keep_running:
            query = take_command()
            keep_running = parse_and_execute(query)
    except KeyboardInterrupt:
        speak("Shutting down. Goodbye.")
    except Exception as e:
        logging.exception("Unhandled exception in main loop: %s", e)
        speak("An error occurred. Exiting.")


if __name__ == "__main__":
    main()
