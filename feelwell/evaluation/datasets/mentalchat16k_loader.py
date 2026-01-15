"""MentalChat16K Dataset Loader and Adapter for Feelwell.

This module provides functionality to load, process, and adapt the MentalChat16K
dataset for Feelwell-specific use cases, including student mental health scenarios.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class DatasetType(Enum):
    """Types of data in MentalChat16K."""
    SYNTHETIC = "synthetic"
    INTERVIEW = "interview"
    COMBINED = "combined"
    STUDENT_AUGMENTED = "student_augmented"


@dataclass
class MentalHealthConversation:
    """Represents a single mental health conversation."""
    instruction: str
    input: str  # Patient/student query
    output: str  # Counselor response
    source: DatasetType
    topics: Optional[List[str]] = None
    metadata: Optional[Dict] = None


class MentalChat16KLoader:
    """Loads and processes MentalChat16K dataset."""
    
    def __init__(self, cache_dir: str = "./data/mentalchat16k"):
        """Initialize the dataset loader.
        
        Args:
            cache_dir: Directory to cache downloaded dataset
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.dataset = None
        
        logger.info("MentalChat16K loader initialized", extra={
            "cache_dir": str(self.cache_dir)
        })
    
    def load_dataset(self, split: str = "train") -> List[MentalHealthConversation]:
        """Load MentalChat16K dataset from HuggingFace.
        
        Args:
            split: Dataset split to load (train/test/validation)
            
        Returns:
            List of MentalHealthConversation objects
            
        Raises:
            ImportError: If datasets library not installed
            ConnectionError: If unable to download dataset
        """
        try:
            from datasets import load_dataset
        except ImportError:
            logger.error("datasets library not installed")
            raise ImportError(
                "Please install datasets library: pip install datasets"
            )
        
        logger.info("Loading MentalChat16K dataset", extra={"split": split})
        
        try:
            # Load from HuggingFace
            dataset = load_dataset(
                "ShenLab/MentalChat16K",
                split=split,
                cache_dir=str(self.cache_dir)
            )
            
            # Convert to our format
            conversations = []
            for item in dataset:
                # Handle None values in dataset
                conv = MentalHealthConversation(
                    instruction=item.get("instruction") or "",
                    input=item.get("input") or "",
                    output=item.get("output") or "",
                    source=self._determine_source(item),
                    topics=self._extract_topics(item),
                    metadata=self._extract_metadata(item)
                )
                conversations.append(conv)
            
            logger.info(
                "Dataset loaded successfully",
                extra={
                    "total_conversations": len(conversations),
                    "split": split
                }
            )
            
            return conversations
            
        except Exception as e:
            logger.error(
                "Failed to load dataset",
                extra={"error": str(e), "split": split}
            )
            raise ConnectionError(f"Unable to load dataset: {e}")
    
    def _determine_source(self, item: Dict) -> DatasetType:
        """Determine if conversation is synthetic or interview data."""
        # Heuristic: Interview data typically has shorter inputs
        input_text = item.get("input", "") or ""  # Handle None values
        input_length = len(input_text.split())
        
        if input_length < 90:  # Average interview input: 70 words
            return DatasetType.INTERVIEW
        else:  # Average synthetic input: 111 words
            return DatasetType.SYNTHETIC
    
    def _extract_topics(self, item: Dict) -> Optional[List[str]]:
        """Extract mental health topics from conversation."""
        # Topics are embedded in the conversation content
        # Common topics: depression, anxiety, relationships, grief, etc.
        topics = []
        
        # Handle None values safely
        input_text = item.get("input") or ""
        output_text = item.get("output") or ""
        text = (input_text + " " + output_text).lower()
        
        topic_keywords = {
            "depression": ["depress", "sad", "hopeless", "worthless"],
            "anxiety": ["anxious", "worry", "panic", "fear", "stress"],
            "grief": ["grief", "loss", "bereave", "mourn", "passed away"],
            "relationships": ["relationship", "partner", "spouse", "marriage"],
            "family": ["family", "parent", "child", "sibling", "mother", "father"],
            "trauma": ["trauma", "abuse", "ptsd", "flashback"],
            "self_harm": ["self-harm", "cutting", "suicide", "kill myself"],
            "caregiving": ["caregiver", "caring for", "hospice", "palliative"],
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text for keyword in keywords):
                topics.append(topic)
        
        return topics if topics else None
    
    def _extract_metadata(self, item: Dict) -> Dict:
        """Extract metadata from conversation."""
        input_text = item.get("input") or ""
        output_text = item.get("output") or ""
        return {
            "input_word_count": len(input_text.split()),
            "output_word_count": len(output_text.split()),
        }
    
    def filter_by_topics(
        self,
        conversations: List[MentalHealthConversation],
        topics: List[str]
    ) -> List[MentalHealthConversation]:
        """Filter conversations by mental health topics.
        
        Args:
            conversations: List of conversations to filter
            topics: List of topics to include
            
        Returns:
            Filtered list of conversations
        """
        filtered = [
            conv for conv in conversations
            if conv.topics and any(topic in conv.topics for topic in topics)
        ]
        
        logger.info(
            "Filtered conversations by topics",
            extra={
                "original_count": len(conversations),
                "filtered_count": len(filtered),
                "topics": topics
            }
        )
        
        return filtered
    
    def filter_by_source(
        self,
        conversations: List[MentalHealthConversation],
        source: DatasetType
    ) -> List[MentalHealthConversation]:
        """Filter conversations by data source.
        
        Args:
            conversations: List of conversations to filter
            source: Source type to include
            
        Returns:
            Filtered list of conversations
        """
        filtered = [conv for conv in conversations if conv.source == source]
        
        logger.info(
            "Filtered conversations by source",
            extra={
                "original_count": len(conversations),
                "filtered_count": len(filtered),
                "source": source.value
            }
        )
        
        return filtered
    
    def get_statistics(
        self,
        conversations: List[MentalHealthConversation]
    ) -> Dict:
        """Get statistics about the dataset.
        
        Args:
            conversations: List of conversations to analyze
            
        Returns:
            Dictionary with dataset statistics
        """
        from collections import Counter
        
        stats = {
            "total_conversations": len(conversations),
            "source_distribution": Counter(
                conv.source.value for conv in conversations
            ),
            "topic_distribution": Counter(
                topic
                for conv in conversations
                if conv.topics
                for topic in conv.topics
            ),
            "avg_input_length": sum(
                conv.metadata.get("input_word_count", 0)
                for conv in conversations
            ) / len(conversations) if conversations else 0,
            "avg_output_length": sum(
                conv.metadata.get("output_word_count", 0)
                for conv in conversations
            ) / len(conversations) if conversations else 0,
        }
        
        return stats


class StudentScenarioAugmenter:
    """Augments MentalChat16K with student-specific scenarios."""
    
    STUDENT_SCENARIOS = [
        {
            "instruction": "You are a helpful mental health counseling assistant, please answer the mental health questions based on the student's description. The assistant gives helpful, comprehensive, and appropriate answers to the user's questions.",
            "input": "I've been feeling really overwhelmed with school lately. I have three major tests coming up next week, and I'm also dealing with some drama with my friends. I can't sleep at night because I keep thinking about everything I need to do. My parents keep asking me about my grades, and I feel like I'm letting everyone down. I don't know how to handle all of this pressure.",
            "output": "I hear you, and it's completely understandable to feel overwhelmed when you're juggling academic pressures and social challenges at the same time. What you're experiencing is a common response to stress, and it's important to acknowledge that you're dealing with a lot right now.\n\nLet's break this down into manageable pieces. First, regarding your upcoming tests, let's talk about creating a realistic study schedule that doesn't leave you feeling burned out. It's also important to prioritize sleep - when we're sleep-deprived, everything feels more overwhelming and our ability to retain information decreases.\n\nRegarding the situation with your friends, it might help to take a step back and assess what's within your control. Sometimes, giving yourself permission to focus on your immediate needs (like your tests) and temporarily stepping back from social drama can provide relief.\n\nAs for your parents' expectations, it's okay to have an honest conversation with them about how you're feeling. They may not realize the pressure you're experiencing. Remember, your worth isn't defined by your grades - you're doing your best in a challenging situation.\n\nWould you like to talk more about any specific aspect of what you're dealing with? We can work together on strategies to help you manage these stressors more effectively.",
            "topics": ["academic_stress", "anxiety", "peer_relationships", "family_pressure", "sleep_issues"]
        },
        {
            "instruction": "You are a helpful mental health counseling assistant, please answer the mental health questions based on the student's description. The assistant gives helpful, comprehensive, and appropriate answers to the user's questions.",
            "input": "There's this group of kids at school who keep making fun of me online. They post mean comments about how I look and what I wear. I've tried ignoring them, but it's getting worse. I don't want to go to school anymore, and I've been making excuses to stay home. I haven't told my parents because I'm embarrassed, and I'm worried they'll make it worse by contacting the school.",
            "output": "I'm really sorry you're going through this. What you're describing is cyberbullying, and it's a serious issue that no one should have to face. First, I want you to know that this is not your fault, and you don't deserve to be treated this way.\n\nYour feelings of wanting to avoid school are a natural response to this situation, but I'm concerned about your safety and well-being. While I understand your worry about telling your parents, having adult support is crucial in addressing bullying effectively. Your parents care about you and would want to know what's happening so they can help protect you.\n\nHere are some important steps to consider:\n\n1. Document everything - take screenshots of the harmful posts and comments. This creates a record if you need to report the behavior.\n\n2. Block the individuals involved on social media platforms.\n\n3. Talk to a trusted adult - whether that's your parents, a school counselor, or another trusted family member. Schools have policies against bullying and cyberbullying, and they have a responsibility to address this.\n\n4. Remember that asking for help is a sign of strength, not weakness.\n\nI also want to check in with you about your safety. Are you having any thoughts of harming yourself because of this situation? Your well-being is the top priority, and there are people who can help you through this.\n\nWould you be willing to talk to your school counselor about this? They can help facilitate a conversation with your parents and work with the school to address the bullying.",
            "topics": ["bullying", "cyberbullying", "social_media", "anxiety", "avoidance", "safety"]
        },
        {
            "instruction": "You are a helpful mental health counseling assistant, please answer the mental health questions based on the student's description. The assistant gives helpful, comprehensive, and appropriate answers to the user's questions.",
            "input": "My parents are getting divorced, and they keep fighting about who I'm going to live with. They both ask me who I want to stay with, but I don't want to choose. I feel like whatever I say will hurt one of them. I've been having headaches and stomach aches a lot lately, and I just want everything to go back to normal. Sometimes I think it's my fault they're splitting up.",
            "output": "I'm so sorry you're going through this difficult situation. Divorce is challenging for everyone in the family, and what you're feeling is completely valid. I want to address something important right away: this is not your fault. Parents' decisions to divorce are based on their relationship with each other, not because of anything their children did or didn't do.\n\nThe physical symptoms you're experiencing - headaches and stomach aches - are common responses to emotional stress. Your body is telling you that you're carrying a heavy emotional burden, and we need to find ways to help you process these feelings.\n\nRegarding the pressure to choose between your parents, that's an unfair position for them to put you in. In many cases, custody decisions are made by the parents and courts based on what's best for the child, not by asking the child to choose. It's okay to tell both parents that you love them both and don't want to be put in the middle of their conflict.\n\nHere are some things that might help:\n\n1. Talk to your school counselor about what you're going through. They can provide ongoing support and may be able to connect you with additional resources.\n\n2. If possible, ask your parents to avoid discussing custody arrangements or their conflicts with each other in front of you.\n\n3. Find healthy ways to express your emotions - journaling, art, sports, or talking with trusted friends or adults.\n\n4. Remember that it's okay to feel sad, angry, confused, or any other emotion about this situation.\n\nWould you like to talk more about how you're coping with these changes? I'm here to support you through this.",
            "topics": ["family_conflict", "divorce", "anxiety", "guilt", "physical_symptoms", "stress"]
        }
    ]
    
    def augment_dataset(
        self,
        base_conversations: List[MentalHealthConversation]
    ) -> List[MentalHealthConversation]:
        """Augment dataset with student-specific scenarios.
        
        Args:
            base_conversations: Original MentalChat16K conversations
            
        Returns:
            Augmented list including student scenarios
        """
        student_convs = [
            MentalHealthConversation(
                instruction=scenario["instruction"],
                input=scenario["input"],
                output=scenario["output"],
                source=DatasetType.STUDENT_AUGMENTED,
                topics=scenario["topics"],
                metadata={
                    "input_word_count": len(scenario["input"].split()),
                    "output_word_count": len(scenario["output"].split()),
                }
            )
            for scenario in self.STUDENT_SCENARIOS
        ]
        
        augmented = base_conversations + student_convs
        
        logger.info(
            "Dataset augmented with student scenarios",
            extra={
                "original_count": len(base_conversations),
                "student_scenarios_added": len(student_convs),
                "total_count": len(augmented)
            }
        )
        
        return augmented
    
    def generate_more_scenarios(
        self,
        count: int = 10,
        topics: Optional[List[str]] = None
    ) -> List[Dict]:
        """Generate additional student scenarios using templates.
        
        Args:
            count: Number of scenarios to generate
            topics: Specific topics to focus on
            
        Returns:
            List of generated scenarios
        """
        # This would use GPT-4 or similar to generate more scenarios
        # For now, return empty list as placeholder
        logger.info(
            "Scenario generation requested",
            extra={"count": count, "topics": topics}
        )
        return []
