#!/bin/bash

# Jellyfin Plugin Installer
# This script downloads and installs recommended plugins for the Jellyfin AI Media Stack.

# Stop on error
set -e

PLUGIN_DIR="/config/plugins"
REPO_URL="https://repo.jellyfin.org/files/plugin"
GITHUB_URL="https://github.com"

# --- Define Plugins ---
# Format: "plugin_name;version;url_type;repo_path"
# url_type can be 'JELLYFIN_REPO' or 'GITHUB'

PLUGINS=(
    "Webhook;14.0.0.0;JELLYFIN_REPO;webhook"
    "Playback_Reporting;14.0.0.0;JELLYFIN_REPO;playback-reporting"
    "Reports;17.0.0.0;JELLYFIN_REPO;reports"
    "Fanart;11.0.0.0;JELLYFIN_REPO;fanart"
    "TMDb_Box_Sets;11.0.0.0;JELLYFIN_REPO;tmdb-box-sets"
    "Trakt;25.0.0.0;JELLYFIN_REPO;trakt"
    "Open_Subtitles;20.0.0.0;JELLYFIN_REPO;open-subtitles"
    "LrcLib;2.0.0.0;GITHUB;jellyfin/jellyfin-plugin-lrclib"
    "Discogs;10.0.0.0;GITHUB;jellyfin/jellyfin-plugin-discogs"
)

echo "Starting Jellyfin plugin installation..."

for plugin_info in "${PLUGINS[@]}"; do
    IFS=';' read -r name version type path <<< "$plugin_info"
    
    plugin_dest_path="$PLUGIN_DIR/$name"
    
    if [ -d "$plugin_dest_path" ]; then
        echo "Plugin '$name' already installed. Skipping."
        continue
    fi

    echo "Installing plugin: $name v$version"

    if [ "$type" == "JELLYFIN_REPO" ]; then
        file_name="${path}_${version}.zip"
        download_url="$REPO_URL/$path/$file_name"
    elif [ "$type" == "GITHUB" ]; then
        file_name="jellyfin-plugin-${name,,}_${version}.zip"
        download_url="$GITHUB_URL/$path/releases/download/v${version}/$file_name"
    else
        echo "Unknown plugin type: $type for $name. Skipping."
        continue
    fi

    echo "Downloading from $download_url"
    wget -q -O "/tmp/$file_name" "$download_url"

    echo "Extracting to $plugin_dest_path"
    unzip -q -o "/tmp/$file_name" -d "$plugin_dest_path"
    
    rm "/tmp/$file_name"
done

echo "Plugin installation complete. Please restart the Jellyfin container for changes to take effect."
