"""
Challenge Service Module

Serviço que coordena a geração de desafios e seu envio para o Redis.
Implementa lógica de negócio e orquestração.
"""

import logging
from typing import Optional

from src.generators.challenge_generator import (
    Challenge,
    ChallengeGenerator,
    ChallengeLevel,
    ChallengeType,
    ChallengeGenerationError,
)
from src.integrations.redis import RedisClient, RedisConnectionError

logger = logging.getLogger(__name__)


class ChallengeServiceError(Exception):
    """Erro no serviço de desafios."""

    pass


class ChallengeService:
    """Serviço de gerenciamento de desafios."""

    def __init__(self, redis_client: Optional[RedisClient] = None):
        """
        Inicializa o serviço de desafios.

        Args:
            redis_client: Cliente Redis (pode ser None para desabilitá-lo)
        """
        self.generator = ChallengeGenerator()
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.logger.info("ChallengeService initialized")

    async def generate_and_save(
        self,
        challenge_type: Optional[ChallengeType] = None,
        level: Optional[ChallengeLevel] = None,
    ) -> Challenge:
        """
        Gera um desafio e o salva no Redis.

        Args:
            challenge_type: Tipo de desafio
            level: Nível de dificuldade

        Returns:
            Challenge: Desafio gerado

        Raises:
            ChallengeServiceError: Erro no serviço
        """
        try:
            challenge = await self.generator.generate(
                challenge_type=challenge_type, level=level
            )
            self.logger.info(f"Challenge generated: {challenge.id}")

            if self.redis_client:
                try:
                    await self.redis_client.push_challenge(challenge)
                    self.logger.info(f"Challenge saved to Redis: {challenge.id}")
                except RedisConnectionError as e:
                    self.logger.warning(
                        f"Failed to save challenge to Redis: {str(e)}. "
                        f"Challenge still generated locally."
                    )

            return challenge

        except ChallengeGenerationError as e:
            error_msg = f"Failed to generate challenge: {str(e)}"
            self.logger.error(error_msg)
            raise ChallengeServiceError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error in generate_and_save: {str(e)}"
            self.logger.error(error_msg)
            raise ChallengeServiceError(error_msg) from e

    async def generate_and_save_batch(
        self,
        count: int = 10,
        challenge_type: Optional[ChallengeType] = None,
    ) -> list[Challenge]:
        """
        Gera múltiplos desafios e os salva no Redis.

        Args:
            count: Quantidade de desafios
            challenge_type: Tipo de desafio

        Returns:
            list[Challenge]: Lista de desafios gerados

        Raises:
            ChallengeServiceError: Erro no serviço
        """
        try:
            challenges = await self.generator.generate_batch(
                count=count, challenge_type=challenge_type
            )
            self.logger.info(f"Batch of {count} challenges generated")

            if self.redis_client:
                try:
                    await self.redis_client.push_challenges_batch(challenges)
                    self.logger.info(
                        f"Batch of {count} challenges saved to Redis successfully"
                    )
                except RedisConnectionError as e:
                    self.logger.warning(
                        f"Failed to save batch to Redis: {str(e)}. "
                        f"Challenges still generated locally."
                    )

            return challenges

        except ChallengeGenerationError as e:
            error_msg = f"Failed to generate batch: {str(e)}"
            self.logger.error(error_msg)
            raise ChallengeServiceError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error in generate_and_save_batch: {str(e)}"
            self.logger.error(error_msg)
            raise ChallengeServiceError(error_msg) from e

    def get_available_types(self) -> list[str]:
        """Retorna os tipos de desafios disponíveis."""
        return ChallengeGenerator.get_available_types()

    def get_available_levels(self) -> list[str]:
        """Retorna os níveis de dificuldade disponíveis."""
        return ChallengeGenerator.get_available_levels()
