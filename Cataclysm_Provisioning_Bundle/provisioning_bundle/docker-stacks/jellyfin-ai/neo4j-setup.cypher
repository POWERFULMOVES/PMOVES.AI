
// Create constraints for better performance and data integrity
CREATE CONSTRAINT media_id_unique IF NOT EXISTS FOR (m:Media) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT analysis_media_id_unique IF NOT EXISTS FOR (a:Analysis) REQUIRE a.media_id IS UNIQUE;
CREATE CONSTRAINT features_media_id_unique IF NOT EXISTS FOR (f:AudioFeatures) REQUIRE f.media_id IS UNIQUE;

// Create indexes for common queries
CREATE INDEX media_name_index IF NOT EXISTS FOR (m:Media) ON (m.name);
CREATE INDEX media_type_index IF NOT EXISTS FOR (m:Media) ON (m.type);
CREATE INDEX features_tempo_index IF NOT EXISTS FOR (f:AudioFeatures) ON (f.tempo);
CREATE INDEX features_genre_index IF NOT EXISTS FOR (a:Analysis) ON (a.genre);

// Create sample data structure relationships
MATCH (m:Media)-[:HAS_ANALYSIS]->(a:Analysis)
MATCH (m)-[:HAS_FEATURES]->(f:AudioFeatures)
WHERE f.tempo IS NOT NULL AND a.ai_analysis IS NOT NULL
WITH m, a, f
CREATE (g:Genre {name: coalesce(a.ai_analysis.genre, 'Unknown')})
MERGE (m)-[:BELONGS_TO_GENRE]->(g);

// Create similarity relationships based on audio features
MATCH (m1:Media)-[:HAS_FEATURES]->(f1:AudioFeatures)
MATCH (m2:Media)-[:HAS_FEATURES]->(f2:AudioFeatures)
WHERE m1.id <> m2.id 
  AND abs(f1.tempo - f2.tempo) < 10
  AND abs(f1.spectral_centroid_mean - f2.spectral_centroid_mean) < 500
CREATE (m1)-[:SIMILAR_TO {score: 1.0 / (1.0 + abs(f1.tempo - f2.tempo) + abs(f1.spectral_centroid_mean - f2.spectral_centroid_mean) / 1000)}]->(m2);

// Create playlists based on content analysis
MATCH (m:Media)-[:HAS_ANALYSIS]->(a:Analysis)
WHERE a.ai_analysis.mood IS NOT NULL
WITH a.ai_analysis.mood as mood, collect(m) as media_items
CREATE (p:Playlist {name: mood + ' Playlist', mood: mood, created_at: datetime()})
FOREACH (media IN media_items | CREATE (p)-[:CONTAINS]->(media));

// Create artist relationships (if available in metadata)
MATCH (m:Media)
WHERE m.artist IS NOT NULL
MERGE (artist:Artist {name: m.artist})
CREATE (artist)-[:PERFORMED]->(m);

// Create album relationships (if available in metadata)
MATCH (m:Media)
WHERE m.album IS NOT NULL
MERGE (album:Album {name: m.album})
CREATE (album)-[:CONTAINS]->(m);
