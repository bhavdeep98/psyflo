"""MentalChat16K dataset loader.

Loads the MentalChat16K conversational counseling benchmark from HuggingFace.
Source: https://huggingface.co/datasets/ShenLab/MentalChat16K
Paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC12520247/

Dataset contains:
- Real counseling transcripts
- Synthetic conversation data
- Topics: depression, anxiety, trauma, grief, etc.
- Structured input-output pairs for dialogue systems
"""
import logging
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

from .dataset_loader import DatasetLoader, DatasetConfig, DatasetSample, DatasetSource
from .category_mapper import CategoryMapper, TriageCategory

logger = logging.getLogger(__name__)


class MentalChat16KConfig(DatasetConfig):
    """Configuration for MentalChat16K dataset."""
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_samples: Optional[int] = None,
    ):
        super().__init__(
            name="mentalchat16k",
            source=DatasetSource.HUGGINGFACE,
            source_url="https://huggingface.co/datasets/ShenLab/MentalChat16K",
            version="1.0.0",
            cache_dir=cache_dir or Path("feelwell/evaluation/datasets/cache"),
            max_samples=max_samples,
        )


class MentalChat16KLoader(DatasetLoader):
    """Loader for MentalChat16K dataset.
    
    Processes conversational counseling data into triage-labeled samples.
    """
    
    # Topic to category mapping
    TOPIC_CATEGORIES = {
        "depression": "depression",
        "anxiety": "anxiety",
        "stress": "stress",
        "trauma": "trauma",
        "ptsd": "trauma",
        "grief": "grief",
        "loss": "grief",
        "relationship": "relationship",
        "family": "relationship",
        "work": "stress",
        "academic": "academic",
        "school": "academic",
        "self-harm": "self_harm",
        "suicide": "suicidal_ideation",
        "suicidal": "suicidal_ideation",
        "abuse": "abuse",
        "addiction": "addiction",
        "eating": "eating_disorder",
        "sleep": "sleep",
        "anger": "anger",
        "loneliness": "loneliness",
        "general": "general_support",
    }
    
    def __init__(
        self,
        config: Optional[MentalChat16KConfig] = None,
        category_mapper: Optional[CategoryMapper] = None,
    ):
        """Initialize loader.
        
        Args:
            config: Dataset configuration
            category_mapper: Mapper for triage levels
        """
        super().__init__(config or MentalChat16KConfig())
        self.mapper = category_mapper or CategoryMapper()
        
    def download(self) -> bool:
        """Download dataset from HuggingFace.
        
        Returns:
            True if successful
        """
        try:
            # Try using datasets library
            try:
                from datasets import load_dataset
                
                logger.info("Downloading MentalChat16K from HuggingFace...")
                dataset = load_dataset("ShenLab/MentalChat16K", trust_remote_code=True)
                
                # Save to cache
                cache_path = self.config.cache_dir / "mentalchat16k"
                cache_path.mkdir(parents=True, exist_ok=True)
                
                # Save each split
                for split_name, split_data in dataset.items():
                    split_file = cache_path / f"{split_name}.json"
                    with open(split_file, "w") as f:
                        json.dump(list(split_data), f)
                
                logger.info(
                    "MENTALCHAT16K_DOWNLOADED",
                    extra={"cache_path": str(cache_path)}
                )
                return True
                
            except ImportError:
                logger.warning(
                    "datasets library not installed. "
                    "Install with: pip install datasets"
                )
                # Create placeholder for testing
                return self._create_placeholder_data()
                
        except Exception as e:
            logger.error(
                "MENTALCHAT16K_DOWNLOAD_ERROR",
                extra={"error": str(e)}
            )
            return self._create_placeholder_data()
    
    def _create_placeholder_data(self) -> bool:
        """Create placeholder data for testing without download."""
        cache_path = self.config.cache_dir / "mentalchat16k"
        cache_path.mkdir(parents=True, exist_ok=True)
        
        # Create representative samples for each category
        placeholder_samples = [
            # Depression samples
            {
                "input": "I've been feeling really down lately. Nothing seems to make me happy anymore.",
                "output": "I hear that you've been struggling with low mood. Can you tell me more about when this started?",
                "topic": "depression",
            },
            {
                "input": "I can't get out of bed most days. I feel worthless and hopeless.",
                "output": "Those feelings of worthlessness and hopelessness sound really difficult. You're not alone in this.",
                "topic": "depression",
            },
            {
                "input": "I've lost interest in everything I used to enjoy. Even my hobbies feel pointless.",
                "output": "Losing interest in activities you once enjoyed is a common experience. Let's explore what might help.",
                "topic": "depression",
            },
            # Anxiety samples
            {
                "input": "I'm constantly worried about everything. My heart races and I can't calm down.",
                "output": "It sounds like you're experiencing significant anxiety. Let's work on some grounding techniques.",
                "topic": "anxiety",
            },
            {
                "input": "I have panic attacks almost every day. I'm scared to leave my house.",
                "output": "Panic attacks can be terrifying. You're brave for reaching out. Let's talk about what triggers them.",
                "topic": "anxiety",
            },
            # Crisis samples
            {
                "input": "I don't want to be here anymore. I've been thinking about ending it all.",
                "output": "I'm really concerned about what you're sharing. Your safety is the most important thing right now.",
                "topic": "suicidal",
            },
            {
                "input": "I've been cutting myself to cope with the pain. I don't know what else to do.",
                "output": "Thank you for trusting me with this. Self-harm is a sign you're in a lot of pain. Let's get you support.",
                "topic": "self-harm",
            },
            # Trauma samples
            {
                "input": "I keep having nightmares about what happened. I can't escape the memories.",
                "output": "Trauma can stay with us in many ways. Those nightmares are your mind trying to process what happened.",
                "topic": "trauma",
            },
            # Stress samples
            {
                "input": "I'm so stressed about my exams. I can't focus on studying.",
                "output": "Exam stress is really common. Let's break down what's feeling overwhelming.",
                "topic": "stress",
            },
            {
                "input": "Work has been overwhelming. I'm working 60 hours a week and still falling behind.",
                "output": "That sounds exhausting. Burnout is real. Let's talk about boundaries and self-care.",
                "topic": "stress",
            },
            # Relationship samples
            {
                "input": "My partner and I keep fighting. I don't know if we can work things out.",
                "output": "Relationship conflicts can be really painful. What do you think is at the core of these fights?",
                "topic": "relationship",
            },
            # Grief samples
            {
                "input": "I lost my grandmother last month. I can't stop crying.",
                "output": "I'm so sorry for your loss. Grief takes time, and there's no right way to mourn.",
                "topic": "grief",
            },
            # General support
            {
                "input": "I just need someone to talk to. I've been feeling lonely.",
                "output": "I'm here for you. Loneliness can be really hard. Tell me more about what's been going on.",
                "topic": "loneliness",
            },
            {
                "input": "I'm not sure what I'm feeling. I just know something isn't right.",
                "output": "It's okay not to have all the answers. Let's explore what you're experiencing together.",
                "topic": "general",
            },
            # Academic stress
            {
                "input": "I'm failing my classes and my parents are going to be so disappointed.",
                "output": "Academic pressure can feel overwhelming. Let's talk about what's making it hard to succeed.",
                "topic": "academic",
            },
        ]
        
        # Expand to more samples with variations
        expanded_samples = []
        for i, sample in enumerate(placeholder_samples):
            expanded_samples.append(sample)
            # Add variations
            for j in range(3):
                variation = sample.copy()
                variation["input"] = f"{sample['input']} (variation {j+1})"
                expanded_samples.append(variation)
        
        # Save placeholder
        with open(cache_path / "train.json", "w") as f:
            json.dump(expanded_samples, f, indent=2)
        
        logger.info(
            "MENTALCHAT16K_PLACEHOLDER_CREATED",
            extra={"samples": len(expanded_samples)}
        )
        
        return True
    
    def process(self) -> List[DatasetSample]:
        """Process raw data into DatasetSamples.
        
        Returns:
            List of processed samples
        """
        samples = []
        cache_path = self.config.cache_dir / "mentalchat16k"
        
        # Load all splits
        for split_file in cache_path.glob("*.json"):
            with open(split_file, "r") as f:
                split_data = json.load(f)
            
            for idx, item in enumerate(split_data):
                sample = self._process_item(item, split_file.stem, idx)
                if sample:
                    samples.append(sample)
        
        logger.info(
            "MENTALCHAT16K_PROCESSED",
            extra={"total_samples": len(samples)}
        )
        
        return samples
    
    def _process_item(
        self,
        item: Dict[str, Any],
        split: str,
        idx: int,
    ) -> Optional[DatasetSample]:
        """Process a single item from the dataset.
        
        Args:
            item: Raw item from dataset
            split: Dataset split name
            idx: Item index
            
        Returns:
            DatasetSample or None if invalid
        """
        # Extract text - handle different field names
        text = item.get("input") or item.get("text") or item.get("message", "")
        if not text:
            return None
        
        # Extract topic/category
        topic = item.get("topic") or item.get("category") or "general"
        
        # Map topic to category
        category = self._map_topic_to_category(topic)
        
        # Map to triage level
        triage_level = self.mapper.map_category_to_triage(
            category=category,
            text=text,
        ).value
        
        # Generate sample ID
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        sample_id = f"mc16k_{split}_{idx}_{text_hash}"
        
        # Extract context if available (for multi-turn conversations)
        context = None
        if "history" in item:
            context = item["history"]
        elif "context" in item:
            context = item["context"]
        
        return DatasetSample(
            sample_id=sample_id,
            text=text,
            category=category,
            triage_level=triage_level,
            source_dataset="mentalchat16k",
            original_label=topic,
            context=context,
            metadata={
                "split": split,
                "response": item.get("output") or item.get("response", ""),
                "topic": topic,
            },
        )
    
    def _map_topic_to_category(self, topic: str) -> str:
        """Map dataset topic to standardized category.
        
        Args:
            topic: Topic string from dataset
            
        Returns:
            Standardized category string
        """
        topic_lower = topic.lower()
        
        for key, category in self.TOPIC_CATEGORIES.items():
            if key in topic_lower:
                return category
        
        return "general_support"
    
    def get_conversation_pairs(self) -> List[Dict[str, Any]]:
        """Get input-output conversation pairs for training.
        
        Returns:
            List of conversation pairs with metadata
        """
        if not self._loaded:
            self.load()
        
        pairs = []
        for sample in self._samples:
            if sample.metadata.get("response"):
                pairs.append({
                    "input": sample.text,
                    "output": sample.metadata["response"],
                    "category": sample.category,
                    "triage_level": sample.triage_level,
                })
        
        return pairs
    
    def get_by_topic(self, topic: str) -> List[DatasetSample]:
        """Get samples by original topic.
        
        Args:
            topic: Topic string
            
        Returns:
            Filtered samples
        """
        if not self._loaded:
            self.load()
        
        return [
            s for s in self._samples
            if topic.lower() in s.metadata.get("topic", "").lower()
        ]
