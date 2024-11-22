import requests
import subprocess
import json
import re
import tempfile
import os
import threading
import queue
import time

# Version 7: Running cartesia & llm side by side, one sentence at a time

class CartesiaTTS:
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://api.cartesia.ai/tts/bytes"
        self.headers = {
            "Cartesia-Version": "2024-06-10",
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
    def generate_speech(self, text):
        if not text.strip():
            return
            
        payload = {
            "transcript": text.strip(),
            "model_id": "sonic-english",
            "voice": {
                "mode": "id",
                "id": "a0e99841-438c-4a64-b679-ae501e7d6091"
            },
            "output_format": {
                "container": "wav",
                "encoding": "pcm_f32le",
                "sample_rate": 44100
            }
        }
        
        response = requests.post(
            self.url,
            headers=self.headers,
            json=payload,
            stream=True
        )
        
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            subprocess.run(["aplay", temp_file_path])
            os.unlink(temp_file_path)
        else:
            print(f"Error: {response.status_code} - {response.text}")

def stream_ollama(prompt):
    url = "http://localhost:11434/api/generate"
    data = {
        "model": "smollm:135m",
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
    
    def add_text(self, text):
        self.buffer += text
        
        sentences = []
        last_end = 0
        
        for match in self.sentence_pattern.finditer(self.buffer):
            end_pos = match.end()
            sentence = self.buffer[last_end:end_pos].strip()
            if sentence:
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
    def __init__(self, sentence_queue, print_queue):
        self.sentence_queue = sentence_queue
        self.print_queue = print_queue
        self.sentence_buffer = SentenceBuffer()
        
    def process_text(self, text):
        # Add text to print queue for display
        self.print_queue.put(text)
        
        # Process sentences
        sentences = self.sentence_buffer.add_text(text)
        for sentence in sentences:
            self.sentence_queue.put(sentence)
    
    def finish(self):
        final_text = self.sentence_buffer.flush()
        if final_text:
            self.sentence_queue.put(final_text)
        self.sentence_queue.put(None)  # Signal completion

def text_display_worker(print_queue):
    """Worker thread to handle text display"""
    while True:
        text = print_queue.get()
        if text is None:
            break
        print(text, end='', flush=True)
        print_queue.task_done()

def tts_worker(sentence_queue, tts):
    """Worker thread to handle text-to-speech conversion"""
    while True:
        sentence = sentence_queue.get()
        if sentence is None:
            break
        tts.generate_speech(sentence)
        sentence_queue.task_done()

def main():
    # Initialize queues for inter-thread communication
    sentence_queue = queue.Queue()
    print_queue = queue.Queue()
    
    # Initialize TTS
    api_key = ""
    tts = CartesiaTTS(api_key)
    
    # Ensure audio device is unmuted and volume is set
    subprocess.run(["amixer", "sset", "PCM", "unmute"], check=False)
    subprocess.run(["amixer", "sset", "PCM", "100%"], check=False)
    
    # Initialize text processor
    text_processor = TextProcessor(sentence_queue, print_queue)
    
    # Start worker threads
    tts_thread = threading.Thread(target=tts_worker, args=(sentence_queue, tts))
    display_thread = threading.Thread(target=text_display_worker, args=(print_queue,))
    tts_thread.start()
    display_thread.start()
    
    prompt = "Tell me a short story. Make sure to use proper punctuation and complete sentences."
    print("Starting story generation and speech synthesis...\n")
    
    try:
        # Main thread handles LLM streaming and text processing
        for text_chunk in stream_ollama(prompt):
            text_processor.process_text(text_chunk)
        
        # Clean up
        text_processor.finish()
        print_queue.put(None)  # Signal display thread to finish
        
        # Wait for all threads to complete
        tts_thread.join()
        display_thread.join()
            
    except KeyboardInterrupt:
        print("\nStopping program...")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        # Ensure threads are properly terminated
        sentence_queue.put(None)
        print_queue.put(None)

if __name__ == "__main__":
    main()