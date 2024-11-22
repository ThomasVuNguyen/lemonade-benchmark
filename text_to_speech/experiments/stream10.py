import requests
import subprocess
import json
import re
import threading
import queue
import io
import tempfile
import os
import time

# Version 10: What is the biggest model you can run while still having a real-time experience?

class PiperTTS:
    def __init__(self):
        self.model = "en_US-lessac-medium.onnx"
        self.audio_queue = queue.Queue(maxsize=3)  # Buffer for pre-generated audio
        self.current_process = None
        
    def generate_audio(self, text):
        """Generate audio data without playing it"""
        if not text.strip():
            return None
            
        try:
            # Run piper to generate raw audio
            piper_process = subprocess.Popen(
                ["piper", "--model", self.model, "--output_raw"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Write text and get audio data
            piper_process.stdin.write(text.strip().encode())
            piper_process.stdin.flush()
            piper_process.stdin.close()
            
            audio_data = piper_process.stdout.read()
            piper_process.wait()
            
            return audio_data
            
        except Exception as e:
            print(f"Audio Generation Error: {str(e)}")
            return None
    
    def play_audio(self, audio_data):
        """Play pre-generated audio data"""
        if audio_data:
            try:
                # Play the audio data using aplay
                aplay_process = subprocess.Popen(
                    ["aplay", "-r", "22050", "-f", "S16_LE", "-c", "1"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                aplay_process.stdin.write(audio_data)
                aplay_process.stdin.close()
                aplay_process.wait()
                
            except Exception as e:
                print(f"Audio Playback Error: {str(e)}")

def stream_ollama(prompt):
    url = "http://localhost:11434/api/generate"
    data = {
        "model": "qwen2:0.5b",
        "prompt": prompt,
        "stream": True
    }
    response = requests.post(url, json=data, stream=True)
    for line in response.iter_lines():
        if line:
            yield json.loads(line)['response']

class SentenceBuffer:
    def __init__(self):
        self.buffer = ""
        self.sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])$')
        self.abbreviations = {'Mr.', 'Mrs.', 'Dr.', 'Ms.', 'Prof.', 'Sr.', 'Jr.', 'vs.', 'e.g.', 'i.e.'}
    
    def is_abbreviation(self, text):
        for abbr in self.abbreviations:
            if text.endswith(abbr):
                return True
        return False
    
    def add_text(self, text):
        self.buffer += text
        
        sentences = []
        last_end = 0
        
        for match in self.sentence_pattern.finditer(self.buffer):
            end_pos = match.end()
            sentence = self.buffer[last_end:end_pos].strip()
            
            if sentence and not self.is_abbreviation(sentence):
                sentences.append(sentence)
                last_end = end_pos
        
        if sentences:
            self.buffer = self.buffer[last_end:]
        
        return sentences
    
    def flush(self):
        if self.buffer.strip():
            final_text = self.buffer
            self.buffer = ""
            return final_text
        return None

class TextProcessor:
    def __init__(self, audio_queue, print_queue):
        self.audio_queue = audio_queue
        self.print_queue = print_queue
        self.sentence_buffer = SentenceBuffer()
        self.tts = PiperTTS()
        
    def process_text(self, text):
        self.print_queue.put(text)
        
        sentences = self.sentence_buffer.add_text(text)
        for sentence in sentences:
            # Generate audio data and add to queue
            audio_data = self.tts.generate_audio(sentence)
            if audio_data:
                self.audio_queue.put((sentence, audio_data))
    
    def finish(self):
        final_text = self.sentence_buffer.flush()
        if final_text:
            audio_data = self.tts.generate_audio(final_text)
            if audio_data:
                self.audio_queue.put((final_text, audio_data))
        self.audio_queue.put(None)  # Signal completion

def text_display_worker(print_queue):
    while True:
        text = print_queue.get()
        if text is None:
            break
        print(text, end='', flush=True)
        print_queue.task_done()

def audio_player_worker(audio_queue):
    """Worker thread that plays pre-generated audio"""
    tts = PiperTTS()
    while True:
        item = audio_queue.get()
        if item is None:
            break
        
        sentence, audio_data = item
        tts.play_audio(audio_data)
        audio_queue.task_done()

def main():
    # Initialize queues
    audio_queue = queue.Queue(maxsize=3)  # Limit buffer size
    print_queue = queue.Queue()
    
    # Initialize text processor
    text_processor = TextProcessor(audio_queue, print_queue)
    
    # Ensure audio device is ready
    subprocess.run(["amixer", "sset", "PCM", "unmute"], check=False)
    subprocess.run(["amixer", "sset", "PCM", "100%"], check=False)
    
    # Start worker threads
    audio_thread = threading.Thread(target=audio_player_worker, args=(audio_queue,))
    display_thread = threading.Thread(target=text_display_worker, args=(print_queue,))
    
    audio_thread.daemon = True
    display_thread.daemon = True
    
    audio_thread.start()
    display_thread.start()
    
    prompt = "Tell me about the 'The Creative Act' book. Make sure to use proper punctuation and complete sentences. If you do not have memory of this, do not answer"
    print("Starting story generation and speech synthesis...\n")
    
    try:
        # Main thread handles LLM streaming and text processing
        for text_chunk in stream_ollama(prompt):
            text_processor.process_text(text_chunk)
        
        # Clean up
        text_processor.finish()
        print_queue.put(None)
        
        # Wait for all processing to complete
        audio_queue.join()
        print_queue.join()
            
    except KeyboardInterrupt:
        print("\nStopping program...")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        # Ensure threads are properly terminated
        audio_queue.put(None)
        print_queue.put(None)

if __name__ == "__main__":
    main()