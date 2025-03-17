from confluent_kafka import Producer, Consumer, KafkaError
from dataclasses import dataclass
from datetime import datetime
import json
from typing import Dict, List
import nltk
from collections import Counter
from textblob import TextBlob

@dataclass
class ProcessingStatus:
    file_id: str
    status: str
    timestamp: str
    details: Dict
    
class MonitoringProducer:
    def __init__(self, bootstrap_servers='localhost:9092'):
        self.producer = Producer({
            'bootstrap.servers': bootstrap_servers,
            'client.id': 'monitoring-producer'
        })
        self.status_topic = 'processing_status'
        self.analytics_topic = 'transcript_analytics'
        
    def send_status_update(self, file_id: str, status: str, details: Dict = None):
        status_data = ProcessingStatus(
            file_id=file_id,
            status=status,
            timestamp=datetime.now().isoformat(),
            details=details or {}
        ).__dict__  # Convert to dict for JSON serialization
        
        self.producer.produce(
            self.status_topic,
            value=json.dumps(status_data).encode('utf-8')
        )
        self.producer.flush()
        
    def send_analytics(self, analytics_data: Dict):
        self.producer.produce(
            self.analytics_topic,
            value=json.dumps(analytics_data).encode('utf-8')
        )
        self.producer.flush()

class TranscriptAnalytics:
    def __init__(self):
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('punkt_tab', quiet=True)  
            nltk.download('stopwords', quiet=True)
            self.stop_words = set(nltk.corpus.stopwords.words('english'))
        except Exception as e:
            print(f"Error initializing NLTK: {str(e)}")
            self.stop_words = set()
        
    def analyze_transcript(self, text: str) -> Dict:
        try:
            words = nltk.word_tokenize(text.lower())
            words = [w for w in words if w.isalnum() and w not in self.stop_words]
            
            word_freq = Counter(words).most_common(10)
            
            blob = TextBlob(text)
            sentiment = blob.sentiment.polarity
            
            sentences = nltk.sent_tokenize(text)
            questions = [s for s in sentences if s.strip().endswith('?')]
            
            return {
                'word_count': len(words),
                'unique_words': len(set(words)),
                'top_words': dict(word_freq),
                'interactivity_score': sentiment,
                'question_count': len(questions),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Error in analyze_transcript: {str(e)}")
            return {
                'word_count': 0,
                'unique_words': 0,
                'top_words': {},
                'sentiment_score': 0,
                'question_count': 0,
                'timestamp': datetime.now().isoformat()
            }

class StreamlitMonitoring:
    def __init__(self, bootstrap_servers='localhost:9092'):
        self.consumer = Consumer({
            'bootstrap.servers': bootstrap_servers,
            'group.id': 'streamlit-monitoring-group',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False
        })
        self.topics = ['processing_status', 'transcript_analytics']
        self.status_updates: List[ProcessingStatus] = []
        self.analytics_data: List[Dict] = []
        
    def start_monitoring(self):
        try:
            self.consumer.subscribe(self.topics)
            print(f"Successfully subscribed to topics: {self.topics}")
        except Exception as e:
            print(f"Error in start_monitoring: {str(e)}")
        
    def poll_updates(self, timeout=1.0):
        try:
            msg = self.consumer.poll(timeout)
            if msg is None:
                print("No new messages")
                return None
            print(f"Received raw message: {msg.value()}")
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    return None
                else:
                    print(f"Error: {msg.error()}")
                    return None
            
            data = json.loads(msg.value().decode('utf-8'))
            print(f"Processed message from topic {msg.topic()}: {data}")  # Debug log
            if msg.topic() == 'processing_status':
                status_update = ProcessingStatus(
                    file_id=data['file_id'],
                    status=data['status'],
                    timestamp=data['timestamp'],
                    details=data['details']
                )
                if 'filename' in data['details']:
                    status_update.filename = data['details']['filename']
                self.status_updates.append(status_update)
            else:  # transcript_analytics
                self.analytics_data.append(data)
            self.consumer.commit()
            return msg.topic()
        except Exception as e:
            print(f"Error in poll_updates: {str(e)}")
            return None
        
    def get_latest_status(self, file_id: str) -> ProcessingStatus:
        try:
            relevant_updates = [
                update for update in self.status_updates 
                if update.file_id == file_id
            ]
            return relevant_updates[-1] if relevant_updates else None
        except Exception as e:
            print(f"Error in get_latest_status: {str(e)}")
            return None
        
    def get_analytics_summary(self) -> Dict:
        try:
            print(f"Analytics data count: {len(self.analytics_data)}")  # Debug log
            if not self.analytics_data:
                return {}
            
            total_words = sum(d['word_count'] for d in self.analytics_data)
            avg_sentiment = sum(d['sentiment_score'] for d in self.analytics_data) / len(self.analytics_data)
            
            all_words = {}
            for d in self.analytics_data:
                for w, freq in d['top_words'].items():
                    all_words[w] = all_words.get(w, 0) + freq
            
            return {
                'total_transcripts': len(self.analytics_data),
                'total_words': total_words,
                'average_words_per_transcript': total_words / len(self.analytics_data),
                'overall_sentiment': avg_sentiment,
                'most_common_words': dict(Counter(all_words).most_common(10))
            }
        except Exception as e:
            print(f"Error in get_analytics_summary: {str(e)}")
            return {}