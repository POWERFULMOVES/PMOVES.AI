CREATE CONSTRAINT entity_value_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.value IS UNIQUE;
