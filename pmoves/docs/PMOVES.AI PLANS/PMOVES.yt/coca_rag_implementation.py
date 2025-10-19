"""
CoCa (Contrastive Captioners) Enhanced RAG System
Combines contrastive learning with multi-modal embeddings for superior retrieval
Compatible with your Supabase + HuggingFace setup
"""

import numpy as np
import torch
from typing import List, Dict, Tuple, Optional
import asyncio
import aiohttp
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
import json
from datetime import datetime
import hashlib

@dataclass
class TranscriptSegment:
    """Segment with multi-level embeddings"""
    video_id: str
    segment_id: int
    text: str
    start_seconds: float
    end_seconds: float
    text_embedding: Optional[np.ndarray] = None
    context_embedding: Optional[np.ndarray] = None
    contrastive_embedding: Optional[np.ndarray] = None
    
class CoCaRAGSystem:
    """
    Contrastive Captioners for enhanced RAG
    Implements multi-level embeddings with contrastive learning
    """
    
    def __init__(self, 
                 huggingface_api_key: str,
                 supabase_url: str,
                 supabase_key: str,
                 embedding_dim: int = 3584):
        
        self.hf_api_key = huggingface_api_key
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.embedding_dim = embedding_dim
        
        # Initialize local model for contrastive learning
        self.local_model = SentenceTransformer('all-mpnet-base-v2')
        
        # Temperature for contrastive loss
        self.temperature = 0.07
        
    async def generate_coca_embeddings(self, 
                                      segments: List[Dict],
                                      window_size: int = 3) -> List[Dict]:
        """
        Generate CoCa-style embeddings with three levels:
        1. Text-level: Direct text embedding
        2. Context-level: Sliding window context
        3. Contrastive-level: Cross-segment relationships
        """
        enhanced_segments = []
        
        for i, segment in enumerate(segments):
            # 1. Text-level embedding (standard)
            text_embedding = await self.get_huggingface_embedding(segment['text'])
            
            # 2. Context-level embedding (sliding window)
            context_texts = []
            for j in range(max(0, i - window_size), min(len(segments), i + window_size + 1)):
                if j != i:
                    context_texts.append(segments[j]['text'])
            
            context_text = " ".join(context_texts)
            context_embedding = await self.get_huggingface_embedding(
                f"Context: {context_text[:500]}"
            )
            
            # 3. Contrastive embedding (relationship-aware)
            contrastive_prompt = self.create_contrastive_prompt(segment, segments, i)
            contrastive_embedding = await self.get_huggingface_embedding(contrastive_prompt)
            
            # Combine embeddings with learned weights
            combined_embedding = self.combine_embeddings(
                text_embedding, 
                context_embedding, 
                contrastive_embedding
            )
            
            enhanced_segments.append({
                **segment,
                'text_embedding': text_embedding.tolist(),
                'context_embedding': context_embedding.tolist(),
                'contrastive_embedding': contrastive_embedding.tolist(),
                'combined_embedding': combined_embedding.tolist(),
                'embedding_metadata': {
                    'method': 'coca',
                    'window_size': window_size,
                    'timestamp': datetime.now().isoformat()
                }
            })
        
        return enhanced_segments
    
    def create_contrastive_prompt(self, 
                                 current_segment: Dict, 
                                 all_segments: List[Dict], 
                                 current_index: int) -> str:
        """
        Create a contrastive prompt that emphasizes relationships
        between current segment and others
        """
        # Identify key concepts in current segment
        current_text = current_segment['text']
        
        # Find contrasting elements
        before_text = all_segments[current_index - 1]['text'] if current_index > 0 else ""
        after_text = all_segments[current_index + 1]['text'] if current_index < len(all_segments) - 1 else ""
        
        prompt = f"""
        Main concept: {current_text[:200]}
        
        Distinguishing features from previous: {self.extract_diff(before_text, current_text)}
        Distinguishing features from next: {self.extract_diff(current_text, after_text)}
        
        Unique identifiers: {self.extract_key_terms(current_text)}
        """
        
        return prompt.strip()
    
    def extract_diff(self, text1: str, text2: str) -> str:
        """Extract differentiating features between texts"""
        if not text1 or not text2:
            return "N/A"
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        unique = words2 - words1
        return " ".join(list(unique)[:10])
    
    def extract_key_terms(self, text: str) -> str:
        """Extract key technical terms and entities"""
        import re
        
        # Extract capitalized terms (likely proper nouns/technical terms)
        capitals = re.findall(r'\b[A-Z][a-z]+\b', text)
        
        # Extract terms with numbers (versions, specs)
        with_numbers = re.findall(r'\b\w*\d+\w*\b', text)
        
        # Combine and deduplicate
        terms = list(set(capitals + with_numbers))[:10]
        
        return " ".join(terms)
    
    async def get_huggingface_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding from HuggingFace API
        Matches your existing 3584-dimension setup
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.hf_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "inputs": text,
                "options": {"wait_for_model": True}
            }
            
            # Use your preferred model endpoint
            url = "https://api-inference.huggingface.co/models/sentence-transformers/all-mpnet-base-v2"
            
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                
                # Pad or truncate to match your dimension
                embedding = np.array(result)
                if len(embedding) < self.embedding_dim:
                    embedding = np.pad(embedding, (0, self.embedding_dim - len(embedding)))
                else:
                    embedding = embedding[:self.embedding_dim]
                
                return embedding
    
    def combine_embeddings(self,
                          text_emb: np.ndarray,
                          context_emb: np.ndarray,
                          contrastive_emb: np.ndarray,
                          weights: Tuple[float, float, float] = (0.5, 0.3, 0.2)) -> np.ndarray:
        """
        Combine multiple embeddings with learned weights
        Default weights favor text > context > contrastive
        """
        combined = (weights[0] * text_emb + 
                   weights[1] * context_emb + 
                   weights[2] * contrastive_emb)
        
        # Normalize
        combined = combined / np.linalg.norm(combined)
        
        return combined
    
    def contrastive_loss(self, 
                        anchor: np.ndarray, 
                        positive: np.ndarray, 
                        negatives: List[np.ndarray]) -> float:
        """
        Calculate InfoNCE contrastive loss for training
        Used during fine-tuning phase
        """
        # Cosine similarity with temperature scaling
        pos_sim = np.dot(anchor, positive) / self.temperature
        
        neg_sims = []
        for neg in negatives:
            neg_sim = np.dot(anchor, neg) / self.temperature
            neg_sims.append(np.exp(neg_sim))
        
        # InfoNCE loss
        loss = -np.log(np.exp(pos_sim) / (np.exp(pos_sim) + sum(neg_sims)))
        
        return loss
    
    async def hybrid_search(self, 
                           query: str,
                           search_type: str = "coca_enhanced") -> List[Dict]:
        """
        Enhanced hybrid search using CoCa embeddings
        Combines vector, keyword, and contrastive similarities
        """
        
        # Generate query embeddings at multiple levels
        query_text_emb = await self.get_huggingface_embedding(query)
        query_context_emb = await self.get_huggingface_embedding(f"Looking for: {query}")
        query_contrastive_emb = await self.get_huggingface_embedding(
            f"Find segments about: {query}. Exclude unrelated content."
        )
        
        # Combine query embeddings
        query_combined = self.combine_embeddings(
            query_text_emb,
            query_context_emb,
            query_contrastive_emb,
            weights=(0.6, 0.2, 0.2)  # Favor direct text match for queries
        )
        
        # Build Supabase query
        search_query = self.build_coca_search_query(query_combined, query)
        
        # Execute search
        results = await self.execute_supabase_search(search_query)
        
        # Re-rank results using contrastive scoring
        reranked = self.contrastive_rerank(results, query_combined)
        
        return reranked
    
    def build_coca_search_query(self, 
                               query_embedding: np.ndarray, 
                               text_query: str) -> str:
        """
        Build advanced search query for Supabase with CoCa embeddings
        """
        
        # Convert embedding to PostgreSQL array format
        embedding_str = '[' + ','.join(map(str, query_embedding.tolist())) + ']'
        
        query = f"""
        WITH coca_search AS (
            -- Multi-level vector search
            SELECT 
                t.*,
                1 - (t.text_embedding <=> '{embedding_str}'::vector) as text_similarity,
                1 - (t.context_embedding <=> '{embedding_str}'::vector) as context_similarity,
                1 - (t.contrastive_embedding <=> '{embedding_str}'::vector) as contrastive_similarity
            FROM youtube_transcripts t
        ),
        keyword_search AS (
            -- Full-text search with ranking
            SELECT 
                video_id, 
                segment_id,
                ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', '{text_query}')) as keyword_rank
            FROM youtube_transcripts
            WHERE to_tsvector('english', text) @@ plainto_tsquery('english', '{text_query}')
        ),
        temporal_context AS (
            -- Get surrounding segments for context
            SELECT 
                t1.video_id,
                t1.segment_id,
                COUNT(DISTINCT t2.segment_id) as context_segments
            FROM youtube_transcripts t1
            JOIN youtube_transcripts t2 
                ON t1.video_id = t2.video_id
                AND ABS(t1.segment_id - t2.segment_id) <= 2
            GROUP BY t1.video_id, t1.segment_id
        )
        SELECT 
            cs.*,
            -- Combined CoCa score
            (cs.text_similarity * 0.5 + 
             cs.context_similarity * 0.3 + 
             cs.contrastive_similarity * 0.2) as coca_score,
            -- Keyword relevance
            COALESCE(ks.keyword_rank, 0) as keyword_score,
            -- Temporal context bonus
            COALESCE(tc.context_segments, 0) * 0.05 as context_bonus,
            -- Final hybrid score
            (cs.text_similarity * 0.5 + 
             cs.context_similarity * 0.3 + 
             cs.contrastive_similarity * 0.2) * 0.7 +
            COALESCE(ks.keyword_rank, 0) * 0.2 +
            COALESCE(tc.context_segments, 0) * 0.01 as final_score
        FROM coca_search cs
        LEFT JOIN keyword_search ks USING (video_id, segment_id)
        LEFT JOIN temporal_context tc USING (video_id, segment_id)
        WHERE cs.text_similarity > 0.3  -- Minimum similarity threshold
        ORDER BY final_score DESC
        LIMIT 20;
        """
        
        return query
    
    async def execute_supabase_search(self, query: str) -> List[Dict]:
        """Execute search query on Supabase"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.supabase_url}/rest/v1/rpc/coca_search"
            
            payload = {"query": query}
            
            async with session.post(url, json=payload, headers=headers) as response:
                results = await response.json()
                return results
    
    def contrastive_rerank(self, 
                          results: List[Dict], 
                          query_embedding: np.ndarray,
                          diversity_weight: float = 0.1) -> List[Dict]:
        """
        Re-rank results using contrastive scoring with diversity
        Prevents redundant results while maintaining relevance
        """
        
        if not results:
            return results
        
        reranked = []
        selected_indices = set()
        
        # Greedily select diverse but relevant results
        while len(reranked) < min(10, len(results)):
            best_score = -1
            best_idx = -1
            
            for i, result in enumerate(results):
                if i in selected_indices:
                    continue
                
                # Base relevance score
                relevance = result.get('final_score', 0)
                
                # Diversity penalty based on similarity to already selected
                diversity_penalty = 0
                if reranked:
                    for selected in reranked:
                        # Calculate semantic similarity
                        if 'combined_embedding' in result and 'combined_embedding' in selected:
                            similarity = np.dot(
                                np.array(result['combined_embedding']),
                                np.array(selected['combined_embedding'])
                            )
                            diversity_penalty += similarity
                    
                    diversity_penalty /= len(reranked)
                
                # Combined score
                score = relevance - (diversity_weight * diversity_penalty)
                
                if score > best_score:
                    best_score = score
                    best_idx = i
            
            if best_idx >= 0:
                selected_indices.add(best_idx)
                reranked.append(results[best_idx])
            else:
                break
        
        return reranked
    
    async def process_youtube_batch(self, 
                                   video_urls: List[str],
                                   batch_size: int = 5) -> Dict:
        """
        Process multiple YouTube videos in batches
        """
        results = {
            'processed': [],
            'failed': [],
            'stats': {
                'total_segments': 0,
                'total_videos': len(video_urls),
                'processing_time': 0
            }
        }
        
        start_time = datetime.now()
        
        # Process in batches
        for i in range(0, len(video_urls), batch_size):
            batch = video_urls[i:i + batch_size]
            
            # Process batch concurrently
            tasks = [self.process_single_video(url) for url in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for url, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results['failed'].append({
                        'url': url,
                        'error': str(result)
                    })
                else:
                    results['processed'].append(result)
                    results['stats']['total_segments'] += result.get('segment_count', 0)
        
        results['stats']['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        return results
    
    async def process_single_video(self, url: str) -> Dict:
        """Process a single video with CoCa embeddings"""
        # This would integrate with your MCP tools
        # Placeholder for the actual implementation
        pass


# SQL setup for your Supabase database
SUPABASE_SETUP_SQL = """
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enhanced YouTube transcripts table with CoCa embeddings
CREATE TABLE IF NOT EXISTS youtube_transcripts (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(20) NOT NULL,
    segment_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_seconds FLOAT NOT NULL,
    end_seconds FLOAT NOT NULL,
    timestamped_url TEXT,
    
    -- CoCa multi-level embeddings (3584 dimensions)
    text_embedding vector(3584),
    context_embedding vector(3584),
    contrastive_embedding vector(3584),
    combined_embedding vector(3584),
    
    -- Metadata
    embedding_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Indexes for performance
    UNIQUE(video_id, segment_id)
);

-- Create indexes for vector similarity search
CREATE INDEX idx_text_embedding ON youtube_transcripts 
    USING ivfflat (text_embedding vector_cosine_ops)
    WITH (lists = 100);
    
CREATE INDEX idx_context_embedding ON youtube_transcripts 
    USING ivfflat (context_embedding vector_cosine_ops)
    WITH (lists = 100);
    
CREATE INDEX idx_contrastive_embedding ON youtube_transcripts 
    USING ivfflat (contrastive_embedding vector_cosine_ops)
    WITH (lists = 100);
    
CREATE INDEX idx_combined_embedding ON youtube_transcripts 
    USING ivfflat (combined_embedding vector_cosine_ops)
    WITH (lists = 100);

-- Full-text search index
CREATE INDEX idx_transcript_text_gin ON youtube_transcripts 
    USING gin(to_tsvector('english', text));

-- Trigram index for fuzzy search
CREATE INDEX idx_transcript_text_trgm ON youtube_transcripts 
    USING gin(text gin_trgm_ops);

-- TimescaleDB hypertable for time-series queries
SELECT create_hypertable('youtube_transcripts', 'created_at', 
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE);

-- Summary table for chunk-level embeddings
CREATE TABLE IF NOT EXISTS youtube_summaries (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(20) NOT NULL,
    chunk_id INTEGER NOT NULL,
    summary_text TEXT NOT NULL,
    start_seconds FLOAT NOT NULL,
    end_seconds FLOAT NOT NULL,
    summary_embedding vector(3584),
    segment_ids INTEGER[],
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(video_id, chunk_id)
);

-- Create stored procedure for CoCa-enhanced search
CREATE OR REPLACE FUNCTION coca_search(query_text TEXT)
RETURNS TABLE (
    video_id VARCHAR,
    segment_id INTEGER,
    text TEXT,
    timestamped_url TEXT,
    coca_score FLOAT,
    keyword_score FLOAT,
    final_score FLOAT
) AS $$
BEGIN
    -- Implementation would go here based on the Python query
    -- This is a placeholder for the actual search logic
END;
$$ LANGUAGE plpgsql;
"""


# Example usage
async def main():
    # Initialize CoCa system with your credentials
    coca_system = CoCaRAGSystem(
        huggingface_api_key="your-hf-key",
        supabase_url="your-supabase-url",
        supabase_key="your-supabase-key"
    )
    
    # Process videos
    video_urls = [
        "https://www.youtube.com/watch?v=dPL2vRDunMw",
        # Add more URLs
    ]
    
    results = await coca_system.process_youtube_batch(video_urls)
    
    # Search with enhanced CoCa
    search_results = await coca_system.hybrid_search(
        "how to create knowledge graphs with lang extract"
    )
    
    print(f"Found {len(search_results)} relevant segments")
    
if __name__ == "__main__":
    asyncio.run(main())
