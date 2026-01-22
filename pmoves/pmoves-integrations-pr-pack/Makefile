COMPOSE_CORE=compose/docker-compose.core.yml
COMPOSE_WGER=compose/docker-compose.wger.yml
COMPOSE_FIREFLY=compose/docker-compose.firefly.yml

.PHONY: up up-wger up-firefly up-pbj down logs

up:
	@docker compose -f $(COMPOSE_CORE) up -d

up-wger:
	@docker compose -f $(COMPOSE_CORE) -f $(COMPOSE_WGER) --profile wger up -d

up-firefly:
	@docker compose -f $(COMPOSE_CORE) -f $(COMPOSE_FIREFLY) --profile firefly up -d

up-pbj:
	@docker compose -f $(COMPOSE_CORE) -f $(COMPOSE_WGER) -f $(COMPOSE_FIREFLY) --profile wger --profile firefly up -d

down:
	@docker compose -f $(COMPOSE_CORE) -f $(COMPOSE_WGER) -f $(COMPOSE_FIREFLY) down

logs:
	@docker compose -f $(COMPOSE_CORE) logs -f --tail 200
