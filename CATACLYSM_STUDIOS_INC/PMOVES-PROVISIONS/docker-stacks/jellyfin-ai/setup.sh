#!/bin/bash
set -e

echo "🎵 Setting up Media Analysis Stack..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi


# Create necessary directories
print_status "Creating directory structure..."
mkdir -p media/{music,videos,podcasts}
mkdir -p jellyfin/{config,cache}
mkdir -p neo4j/{data,logs,import,plugins}
mkdir -p qwen/{models,cache}
mkdir -p output
mkdir -p logs
mkdir -p redis/data

# Create necessary directories
print_status "Creating directory structure..."
mkdir -p media/{music,videos,podcasts}
mkdir -p jellyfin/{config,cache}
mkdir -p neo4j/{data,logs,import,plugins}
mkdir -p qwen/{models,cache}
mkdir -p output
mkdir -p logs
mkdir -p redis/data

# Ensure the shared pmoves-net network exists for Supabase connectivity
if ! docker network ls --format '{{.Name}}' | grep -wq "pmoves-net"; then
    print_status "Creating shared pmoves-net network..."
    docker network create pmoves-net
else
    print_status "Using existing pmoves-net network"
fi


# Set permissions
print_status "Setting directory permissions..."
sudo chown -R $USER:$USER jellyfin/ neo4j/ qwen/ output/ logs/ redis/
chmod -R 755 jellyfin/ neo4j/ qwen/ output/ logs/ redis/

# Ensure shared Docker network exists for Supabase connectivity
if ! docker network inspect pmoves-net >/dev/null 2>&1; then
    print_status "Creating shared pmoves-net network..."
    docker network create pmoves-net
else
    print_status "Using existing pmoves-net network"
fi

# Create environment file if it doesn't exist
if [ ! -f .env ]; then
    print_status "Creating environment file..."
    cp .env.template .env
    print_warning "Please edit .env file with your actual configuration values!"
fi

# Download Neo4j plugins
print_status "Setting up Neo4j plugins..."
NEO4J_PLUGINS_DIR="./neo4j/plugins"
if [ ! -f "$NEO4J_PLUGINS_DIR/neo4j-graph-data-science.jar" ]; then
    print_status "Downloading Neo4j Graph Data Science plugin..."
    wget -O "$NEO4J_PLUGINS_DIR/neo4j-graph-data-science-2.5.0.jar" \
        "https://github.com/neo4j/graph-data-science/releases/download/2.5.0/neo4j-graph-data-science-2.5.0.jar"
fi

# Start Supabase (if using local instance)
if grep -q "localhost" .env; then
    print_status "Starting Supabase local development..."
    if command -v supabase &> /dev/null; then
        supabase start
    else
        print_warning "Supabase CLI not found. Using remote instance from .env"
    fi
fi

# Start the stack
print_status "Starting the media stack..."
docker-compose up -d

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 30

# Check service health
print_status "Checking service health..."
services=("jellyfin:8096" "neo4j:7474" "api-gateway:3000")

for service in "${services[@]}"; do
    IFS=':' read -ra ADDR <<< "$service"
    service_name="${ADDR[0]}"
    service_port="${ADDR[1]}"

    if curl -f -s "http://localhost:$service_port" > /dev/null; then
        print_status "$service_name is running ✓"
    else
        print_warning "$service_name might not be ready yet"
    fi
done

# Setup Neo4j database
print_status "Setting up Neo4j database..."
print_warning "Waiting 15 seconds for Neo4j to be ready before running setup script..."
sleep 15
docker-compose exec neo4j cypher-shell -u neo4j -p mediapassword123 < neo4j-setup.cypher || print_warning "Neo4j setup script failed. You may need to run it manually via the Neo4j Browser or by exec-ing into the container."

echo ""
print_status "🎉 Setup complete!"
echo ""
echo "Service URLs:"
echo "  📺 Jellyfin:        http://localhost:8096"
echo "  🌐 Neo4j Browser:   http://localhost:7474"
echo "  🚀 API Gateway:     http://localhost:3000"
echo "  📊 Dashboard:       http://localhost:3001"
echo ""
echo "Next steps:"
echo "  1. Configure Jellyfin by visiting http://localhost:8096"
echo "  2. Add your media files to ./media/ directories"
echo "  3. Update .env file with your Supabase credentials"
echo "  4. Check logs with: docker-compose logs -f"
echo ""
print_warning "Remember to configure your .env file with actual API keys and credentials!"
