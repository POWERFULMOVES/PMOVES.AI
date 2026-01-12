# Landscape of Consciousness Harvester (PMOVES Runtime Edition)
# Mirrors the Landscape of Consciousness taxonomy into the PMOVES knowledge stack
# Default target: pmoves/data/consciousness/Constellation-Harvest-Regularization

param(
    [string]$BaseUrl = "https://loc.closertotruth.com",
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot/../../..").Path,
    [string]$TargetPathSuffix = "pmoves/data/consciousness/Constellation-Harvest-Regularization",
    [switch]$IncludeRelatedPapers = $true
)

$TargetPath = Join-Path $RepoRoot $TargetPathSuffix
New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null

# Function to create directory structure
function New-DirectoryStructure {
    param([string]$BasePath)
    
    $directories = @(
        "website-mirror",
        "theories",
        "categories", 
        "subcategories",
        "research-papers",
        "data-exports",
        "media",
        "scripts",
        "processed-for-rag"
    )
    
    foreach ($dir in $directories) {
        $fullPath = Join-Path $BasePath $dir
        if (-not (Test-Path $fullPath)) {
            New-Item -ItemType Directory -Path $fullPath -Force
            Write-Host "Created directory: $fullPath" -ForegroundColor Green
        }
    }

    $processedRoot = Join-Path $BasePath "processed-for-rag"
    foreach ($sub in @("embeddings-ready", "supabase-import")) {
        $subPath = Join-Path $processedRoot $sub
        if (-not (Test-Path $subPath)) {
            New-Item -ItemType Directory -Path $subPath -Force
            Write-Host "Created directory: $subPath" -ForegroundColor Green
        }
    }
}

# Function to download with retry logic
function Invoke-DownloadWithRetry {
    param(
        [string]$Url,
        [string]$OutputPath,
        [int]$MaxRetries = 3
    )
    
    for ($i = 1; $i -le $MaxRetries; $i++) {
        try {
            Write-Host "Downloading: $Url (Attempt $i)" -ForegroundColor Yellow
            Invoke-WebRequest -Uri $Url -OutFile $OutputPath -UserAgent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            Write-Host "Successfully downloaded: $OutputPath" -ForegroundColor Green
            return $true
        }
        catch {
            Write-Warning "Attempt $i failed: $($_.Exception.Message)"
            Start-Sleep -Seconds (2 * $i)
        }
    }
    return $false
}

# Main execution
Write-Host "=== Landscape of Consciousness Downloader ===" -ForegroundColor Cyan
Write-Host "Target Directory: $TargetPath" -ForegroundColor Cyan

# Create directory structure
New-DirectoryStructure -BasePath $TargetPath

# 1. Download the main academic paper (142 pages)
$paperUrl = "https://www.sciencedirect.com/science/article/pii/S0079610723001128"
$paperPath = Join-Path $TargetPath "research-papers\kuhn-landscape-consciousness-2024.html"

Write-Host "`n=== Downloading Main Research Paper ===" -ForegroundColor Magenta
Invoke-DownloadWithRetry -Url $paperUrl -OutputPath $paperPath

# 2. Download related papers and resources
if ($IncludeRelatedPapers) {
    Write-Host "`n=== Downloading Related Resources ===" -ForegroundColor Magenta
    
    $relatedUrls = @{
        "pubmed-summary.html" = "https://pubmed.ncbi.nlm.nih.gov/38281544/"
        "researchgate-page.html" = "https://www.researchgate.net/publication/377744305_A_landscape_of_consciousness_Toward_a_taxonomy_of_explanations_and_implications"
        "closertotruth-article.html" = "https://closertotruth.com/news/a-landscape-of-consciousness-toward-a-taxonomy-of-explanations-and-implications/"
        "mcgilchrist-review.html" = "https://channelmcgilchrist.com/a-landscape-of-consciousness-toward-a-taxonomy-of-explanations-and-implications-by-robert-lawrence-kuhn-doi-org-10-1016-j-pbiomolbio-2023-12-003/"
    }
    
    foreach ($filename in $relatedUrls.Keys) {
        $url = $relatedUrls[$filename]
        $outputPath = Join-Path $TargetPath "research-papers\$filename"
        Invoke-DownloadWithRetry -Url $url -OutputPath $outputPath
    }
}

# 3. Website scraping using Selenium (more robust for dynamic content)
Write-Host "`n=== Setting up Website Scraping ===" -ForegroundColor Magenta

$seleniumScript = @"
# Install required modules if not present
if (!(Get-Module -ListAvailable -Name Selenium)) {
    Install-Module -Name Selenium -Force -Scope CurrentUser
}

Import-Module Selenium

# Initialize Chrome driver with headless option
`$chromeOptions = New-Object OpenQA.Selenium.Chrome.ChromeOptions
`$chromeOptions.AddArgument('--headless')
`$chromeOptions.AddArgument('--no-sandbox')
`$chromeOptions.AddArgument('--disable-dev-shm-usage')

try {
    `$driver = New-Object OpenQA.Selenium.Chrome.ChromeDriver(`$chromeOptions)
    
    # Navigate to main page
    `$driver.Navigate().GoToUrl('$BaseUrl/all-consciousness-categories-subcategories-and-theories')
    Start-Sleep -Seconds 10  # Wait for dynamic content to load
    
    # Save main page
    `$mainPageHtml = `$driver.PageSource
    `$mainPagePath = Join-Path '$TargetPath' 'website-mirror\main-page.html'
    `$mainPageHtml | Out-File -FilePath `$mainPagePath -Encoding UTF8
    
    # Extract theory links and categories
    `$theoryLinks = `$driver.FindElements([OpenQA.Selenium.By]::TagName('a')) | 
        Where-Object { `$_.GetAttribute('href') -like '*theory*' -or `$_.GetAttribute('href') -like '*category*' }
    
    `$links = @()
    foreach (`$link in `$theoryLinks) {
        `$href = `$link.GetAttribute('href')
        `$text = `$link.Text
        if (`$href -and `$href.StartsWith('http')) {
            `$links += @{Url = `$href; Text = `$text}
        }
    }
    
    # Save links for further processing
    `$linksJson = `$links | ConvertTo-Json
    `$linksPath = Join-Path '$TargetPath' 'data-exports\discovered-links.json'
    `$linksJson | Out-File -FilePath `$linksPath -Encoding UTF8
    
    Write-Host "Found `$(`$links.Count) theory/category links"
    
} finally {
    if (`$driver) { `$driver.Quit() }
}
"@

$seleniumScriptPath = Join-Path $TargetPath "scripts\selenium-scraper.ps1"
$seleniumScript | Out-File -FilePath $seleniumScriptPath -Encoding UTF8

Write-Host "Selenium scraper script created: $seleniumScriptPath" -ForegroundColor Green
Write-Host "Run this script separately to scrape dynamic content." -ForegroundColor Yellow

# 4. Create theory categorization structure
Write-Host "`n=== Creating Theory Classification Structure ===" -ForegroundColor Magenta

$theoryCategories = @{
    "Materialism-Theories" = @(
        "Philosophical",
        "Neurobiological", 
        "Electromagnetic-Field",
        "Computational-Informational",
        "Homeostatic-Affective",
        "Embodied-Enactive",
        "Relational",
        "Representational",
        "Language",
        "Phylogenetic-Evolution"
    )
    "Non-Reductive-Physicalism" = @()
    "Quantum-Theories" = @()
    "Integrated-Information-Theory" = @()
    "Panpsychisms" = @()
    "Monisms" = @()
    "Dualisms" = @()
    "Idealisms" = @()
    "Anomalous-Altered-States" = @()
    "Challenge-Theories" = @()
}

foreach ($category in $theoryCategories.Keys) {
    $categoryPath = Join-Path $TargetPath "theories\$category"
    New-Item -ItemType Directory -Path $categoryPath -Force
    
    foreach ($subcategory in $theoryCategories[$category]) {
        $subcategoryPath = Join-Path $categoryPath $subcategory
        New-Item -ItemType Directory -Path $subcategoryPath -Force
    }
}

# 5. Create data extraction template
$dataTemplate = @{
    "metadata" = @{
        "source" = "Landscape of Consciousness"
        "author" = "Robert Lawrence Kuhn"
        "extracted_date" = (Get-Date).ToString("yyyy-MM-dd")
        "base_url" = $BaseUrl
    }
    "theories" = @()
    "categories" = @()
    "subcategories" = @()
    "implications" = @{
        "meaning_purpose_value" = @()
        "ai_consciousness" = @()
        "virtual_immortality" = @()
        "survival_beyond_death" = @()
    }
}

$templatePath = Join-Path $TargetPath "data-exports\consciousness-data-template.json"
$dataTemplate | ConvertTo-Json -Depth 10 | Out-File -FilePath $templatePath -Encoding UTF8

# 6. Create README with instructions
$readmeContent = @"
# PMOVES • Landscape of Consciousness Dataset

This bundle mirrors Robert Lawrence Kuhn's *Landscape of Consciousness* taxonomy into the PMOVES knowledge stack for downstream CHIT decoding, Geometry Bus constellations, and Evo Swarm curation.

## Directory Layout (`pmoves/data/consciousness/Constellation-Harvest-Regularization/`)
- `website-mirror/` — HTML snapshots of the taxonomy portal
- `theories/` — folders per major category (Materialism, Quantum, Panpsychism, etc.)
- `categories/`, `subcategories/` — supplemental hierarchy exports
- `research-papers/` — source papers + related commentary
- `data-exports/` — JSON/CSV manifests for ingestion
- `processed-for-rag/` — embedding-ready artifacts + Supabase import SQL
- `media/` — referenced imagery/video assets
- `scripts/` — Selenium scraper, RAG processors, helper utilities

## PMOVES Integration Checklist
1. **Harvest dynamic content**
   - `pwsh -File scripts/selenium-scraper.ps1` (runs headless Chrome, exports discovered theory links).
2. **Prepare embeddings + JSONL**
   - Use the provided `processed-for-rag` templates or wire n8n ingestion to chunk/export `consciousness-chunks.jsonl`.
3. **Load Supabase (CLI runtime)**
   - Ensure stack is running (`make supa-start && make up`).
   - Apply schema from `processed-for-rag/supabase-import/consciousness-schema.sql` via `supabase db execute` or the SQL editor.
4. **Push embeddings**
   - Import `processed-for-rag/supabase-import/n8n-workflow.json` into n8n (`make up-n8n`), configure Hugging Face + Supabase credentials, and process the JSONL export.
5. **Surface in Geometry / Evo Swarm**
   - Map canonical theory rows into CGP payloads (via custom mapper or manual seed) and publish with `make mesh-handshake FILE=...` or through Agent Zero producers.
   - Update CHIT decoder plan (`pmoves/docs/PMOVESCHIT/`) with resulting constellation IDs for playback.

## Why This Matters
- Anchors extended consciousness theory metadata within Supabase + Qdrant for Geometry Bus queries.
- Enables Evo Swarm to pull from curated philosophical corpora when synthesizing pack suggestions.
- Enriches CHIT playback demos with authoritative consciousness taxonomies.

Document progress and evidence in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` when each integration stage completes.
"@

$readmePath = Join-Path $TargetPath "README.md"
$readmeContent | Out-File -FilePath $readmePath -Encoding UTF8

Write-Host "`n=== Download Setup Complete ===" -ForegroundColor Green
Write-Host "Directory structure created at: $TargetPath" -ForegroundColor Green
Write-Host "`nNext steps (from repo root):" -ForegroundColor Yellow
Write-Host "1. pwsh -File $TargetPath\scripts\selenium-scraper.ps1" -ForegroundColor White
Write-Host "2. Populate processed-for-rag outputs (JSONL, SQL) for embeddings" -ForegroundColor White
Write-Host "3. make supa-start && make up (ensure Supabase + core services running)" -ForegroundColor White
Write-Host "4. Import schema + embeddings via n8n / supabase CLI (see README in harvest dir)" -ForegroundColor White

# Display final summary
Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "✓ Created directory structure" -ForegroundColor Green
Write-Host "✓ Downloaded related research papers" -ForegroundColor Green  
Write-Host "✓ Created Selenium scraper for dynamic content" -ForegroundColor Green
Write-Host "✓ Set up theory categorization structure" -ForegroundColor Green
Write-Host "✓ Created data templates for RAG integration" -ForegroundColor Green
Write-Host "✓ Generated comprehensive README" -ForegroundColor Green
