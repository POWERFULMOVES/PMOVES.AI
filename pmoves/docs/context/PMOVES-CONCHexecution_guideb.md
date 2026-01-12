
# Complete Execution Guide
## Downloading & Processing Consciousness Theories Database

### Prerequisites
```powershell
# Install required PowerShell modules
Install-Module -Name Selenium -Force -Scope CurrentUser
```

### Step 1: Download Website Content
```powershell
# Navigate to your project directory
cd "C:\Users\russe\Documents\GitHub\PMOVES.AI\pmoves\docs"

# Run the main downloader script
.\Constellation-Harvest-Regularization\consciousness-downloader.ps1

# This creates the full directory structure and downloads static content
```

### Step 2: Extract Dynamic Content  
```powershell
# Run the Selenium scraper for dynamic JavaScript content
.\Constellation-Harvest-Regularization\scripts\selenium-scraper.ps1

# This will take several minutes as it loads and extracts dynamic content
```

### Step 3: Process for RAG Integration
```powershell
# Process downloaded content for your Supabase + Hugging Face setup
.\Constellation-Harvest-Regularization\rag-processor.ps1

# This chunks text and prepares data for embedding
```

### Step 4: Set up Supabase Database
```sql
-- In your Supabase SQL editor, run:
-- File: processed-for-rag/supabase-import/consciousness-schema.sql

-- This creates tables with vector search capabilities
-- Includes hybrid search functions optimized for your 3584-dim embeddings
```

### Step 5: Generate Embeddings with n8n
1. Import the workflow: `processed-for-rag/supabase-import/n8n-workflow.json`
2. Configure your Hugging Face API node
3. Set up Supabase connection
4. Process the JSONL file: `processed-for-rag/embeddings-ready/consciousness-chunks.jsonl`

### Integration with Your Existing Setup

**Supabase Vector Store:**
- Uses your existing 3584-dimension embeddings  
- Compatible with pgvector and TimescaleDB
- Hybrid search combines semantic + keyword matching

**n8n Automation:**
- Connects to your existing Hugging Face embeddings node
- Feeds directly into your Supabase node
- Processes consciousness theories alongside your YouTube transcripts

**RAG Query Examples:**
```sql
-- Semantic search for consciousness theories
SELECT * FROM hybrid_search_consciousness(
    'theories about AI consciousness',
    your_query_embedding_vector,
    0.7, -- semantic weight  
    0.3, -- keyword weight
    10   -- result limit
);

-- Category-filtered search
SELECT * FROM consciousness_theories 
WHERE theory_category = 'Quantum-Theories'
AND embedding <=> your_embedding < 0.5;
```

### File Structure Created
```
Constellation-Harvest-Regularization/
├── website-mirror/          # Static HTML copies
├── theories/               # Organized by category
│   ├── Materialism-Theories/
│   ├── Quantum-Theories/
│   ├── Panpsychisms/
│   └── ...
├── research-papers/        # Academic papers (142-page main paper)
├── data-exports/          # JSON/CSV structured data
├── processed-for-rag/     # Ready for embedding
│   ├── embeddings-ready/  # JSONL and CSV for Hugging Face
│   └── supabase-import/   # Schema and workflow
└── scripts/               # Automation scripts
```

### Benefits for Your RAG System
- **Comprehensive Knowledge Base:** 500+ consciousness theories
- **Structured Categories:** From materialist to idealist approaches  
- **Academic Rigor:** Based on 142-page peer-reviewed paper
- **AI-Relevant:** Direct implications for AI consciousness
- **Hybrid Search Ready:** Optimized for your Supabase setup
- **n8n Compatible:** Integrates with your existing automation

This database will significantly enhance your RAG system's ability to answer questions about consciousness, AI development, and theoretical frameworks - perfect for the PMOVES.AI knowledge base!

# Consciousness Harvest (Context Appendix)

Legacy links should redirect to `pmoves/docs/PMOVESCHIT/PMOVES-CONCHexecution_guide.md`, which contains the full PMOVES-aware workflow.

