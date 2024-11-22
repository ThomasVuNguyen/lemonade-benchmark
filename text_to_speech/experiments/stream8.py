import requests
import subprocess
import json
import re
import threading
import queue
import io

# Version 8: Running piper-tts & llm side by side, one sentence at a time

class PiperTTS:
    def __init__(self):
        self.model = "en_US-lessac-medium.onnx"
    
    def generate_speech(self, text):
        if not text.strip():
            return
            
        try:
            # Create a pipeline of piper and aplay processes
            piper_process = subprocess.Popen(
                ["piper", "--model", self.model, "--output_raw"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            aplay_process = subprocess.Popen(
                ["aplay", "-r", "22050", "-f", "S16_LE", "-c", "1"],
                stdin=piper_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Write text to piper and get audio output
            piper_process.stdin.write(text.strip().encode())
            piper_process.stdin.flush()
            piper_process.stdin.close()
            
            # Wait for processes to complete
            piper_process.wait()
            aplay_process.wait()
            
        except Exception as e:
            print(f"TTS Error: {str(e)}")

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
        # Pattern for sentence endings, handling common abbreviations
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
            
            # Only add if it's a complete sentence and not just an abbreviation
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
    def __init__(self, sentence_queue, print_queue):
        self.sentence_queue = sentence_queue
        self.print_queue = print_queue
        self.sentence_buffer = SentenceBuffer()
        
    def process_text(self, text):
        # Queue text for display
        self.print_queue.put(text)
        
        # Process and queue sentences for TTS
        sentences = self.sentence_buffer.add_text(text)
        for sentence in sentences:
            self.sentence_queue.put(sentence)
    
    def finish(self):
        final_text = self.sentence_buffer.flush()
        if final_text:
            self.sentence_queue.put(final_text)
        self.sentence_queue.put(None)  # Signal completion

def text_display_worker(print_queue):
    """Worker thread for text display"""
    while True:
        text = print_queue.get()
        if text is None:
            break
        print(text, end='', flush=True)
        print_queue.task_done()

def tts_worker(sentence_queue, tts):
    """Worker thread for text-to-speech conversion"""
    while True:
        sentence = sentence_queue.get()
        if sentence is None:
            break
        tts.generate_speech(sentence)
        sentence_queue.task_done()

def main():
    # Initialize queues
    sentence_queue = queue.Queue()
    print_queue = queue.Queue()
    
    # Initialize TTS
    tts = PiperTTS()
    
    # Ensure audio device is unmuted and volume is set
    subprocess.run(["amixer", "sset", "PCM", "unmute"], check=False)
    subprocess.run(["amixer", "sset", "PCM", "100%"], check=False)
    
    # Initialize text processor
    text_processor = TextProcessor(sentence_queue, print_queue)
    
    # Start worker threads
    tts_thread = threading.Thread(target=tts_worker, args=(sentence_queue, tts))
    display_thread = threading.Thread(target=text_display_worker, args=(print_queue,))
    
    tts_thread.daemon = True  # Allow program to exit if thread is still running
    display_thread.daemon = True
    
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
        print_queue.put(None)
        
        # Wait for threads to complete
        sentence_queue.join()
        print_queue.join()
            
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