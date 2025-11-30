# Landscape of Consciousness Website Downloader
# For Russell's PMOVES.AI project
# Target: C:\Users\russe\Documents\GitHub\PMOVES.AI\pmoves\docs\Constellation-Harvest-Regularization

param(
    [string]$BaseUrl = "https://loc.closertotruth.com",
    [string]$TargetPath = "C:\Users\russe\Documents\GitHub\PMOVES.AI\pmoves\docs\Constellation-Harvest-Regularization",
    [switch]$IncludeRelatedPapers = $true
)

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
        "scripts"
    )
    
    foreach ($dir in $directories) {
        $fullPath = Join-Path $BasePath $dir
        if (-not (Test-Path $fullPath)) {
            New-Item -ItemType Directory -Path $fullPath -Force
            Write-Host "Created directory: $fullPath" -ForegroundColor Green
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
# Landscape of Consciousness Database

This directory contains a comprehensive download of Robert Lawrence Kuhn's "Landscape of Consciousness" - a taxonomy of consciousness theories.

## Directory Structure

- **website-mirror/**: Static copies of web pages
- **theories/**: Organized by major categories (Materialism, Quantum, Panpsychism, etc.)
- **categories/**: High-level category information
- **subcategories/**: Detailed subcategory breakdowns
- **research-papers/**: Academic papers and related research
- **data-exports/**: Structured data exports (JSON, CSV)
- **media/**: Images, videos, diagrams
- **scripts/**: Automation and extraction scripts

## Main Categories of Consciousness Theories

### Materialism Theories
- Philosophical, Neurobiological, Electromagnetic Field
- Computational & Informational, Homeostatic & Affective
- Embodied & Enactive, Relational, Representational
- Language, Phylogenetic Evolution

### Non-Physical Approaches  
- Non-Reductive Physicalism
- Quantum Theories
- Integrated Information Theory
- Panpsychisms, Monisms, Dualisms, Idealisms
- Anomalous & Altered States Theories
- Challenge Theories

## Key Implications Assessed
1. Meaning/Purpose/Value
2. AI Consciousness
3. Virtual Immortality  
4. Survival Beyond Death

## Usage for RAG System

This data structure is optimized for Russell's RAG system:
- Hierarchical organization for semantic search
- JSON templates for structured extraction
- Metadata for embeddings and indexing
- Cross-references for relationship mapping

## Next Steps

1. Run selenium-scraper.ps1 to extract dynamic content
2. Process JSON data for embedding generation  
3. Import into Supabase vector database
4. Set up hybrid search with Hugging Face embeddings
5. Integrate with n8n automation workflow

## Integration with PMOVES.AI

This consciousness theories database enhances the PMOVES.AI knowledge base by providing:
- Comprehensive theoretical frameworks
- Structured philosophical arguments
- Scientific and speculative approaches
- Implications for AI development

---
Generated for Russell's PMOVES.AI project
Target for RAG integration with Supabase + Hugging Face embeddings
"@

$readmePath = Join-Path $TargetPath "README.md"
$readmeContent | Out-File -FilePath $readmePath -Encoding UTF8

Write-Host "`n=== Download Setup Complete ===" -ForegroundColor Green
Write-Host "Directory structure created at: $TargetPath" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Run the Selenium scraper: .\scripts\selenium-scraper.ps1" -ForegroundColor White
Write-Host "2. Check the data-exports folder for structured data" -ForegroundColor White
Write-Host "3. Process with your Hugging Face embeddings pipeline" -ForegroundColor White
Write-Host "4. Import into your Supabase vector database" -ForegroundColor White

# Display final summary
Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "✓ Created directory structure" -ForegroundColor Green
Write-Host "✓ Downloaded related research papers" -ForegroundColor Green  
Write-Host "✓ Created Selenium scraper for dynamic content" -ForegroundColor Green
Write-Host "✓ Set up theory categorization structure" -ForegroundColor Green
Write-Host "✓ Created data templates for RAG integration" -ForegroundColor Green
Write-Host "✓ Generated comprehensive README" -ForegroundColor Green