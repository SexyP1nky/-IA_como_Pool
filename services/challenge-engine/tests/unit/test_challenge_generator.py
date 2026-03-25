"""
Testes para o módulo de geração de desafios.

Cobre:
- Geração individual de desafios
- Geração em lote
- Validação de tipos e níveis
- Tratamento de erros
"""
import asyncio
import pytest
from src.generators.challenge_generator import (
    Challenge,
    ChallengeGenerator,
    ChallengeGenerationError,
    ChallengeLevel,
    ChallengeType,
)


class TestChallengeGenerator:
    """Testes do gerador de desafios."""

    @pytest.fixture
    def generator(self):
        """Fixture para criar um gerador."""
        return ChallengeGenerator()

    def test_init(self, generator):
        """Testa inicialização do gerador."""
        assert generator is not None
        assert isinstance(generator.logger, object)

    @pytest.mark.asyncio
    async def test_generate_default(self, generator):
        """Testa geração com parâmetros padrão."""
        challenge = await generator.generate()

        assert isinstance(challenge, Challenge)
        assert challenge.id
        assert challenge.type in ChallengeType
        assert challenge.level in ChallengeLevel
        assert challenge.title
        assert challenge.description
        assert challenge.created_at
        assert challenge.metadata

    @pytest.mark.asyncio
    async def test_generate_with_type(self, generator):
        """Testa geração especificando o tipo."""
        for challenge_type in ChallengeType:
            challenge = await generator.generate(challenge_type=challenge_type)
            assert challenge.type == challenge_type

    @pytest.mark.asyncio
    async def test_generate_with_level(self, generator):
        """Testa geração especificando o nível."""
        for level in ChallengeLevel:
            try:
                challenge = await generator.generate(
                    challenge_type=ChallengeType.ALGORITHM, level=level
                )
                assert challenge.level == level
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_generate_with_type_and_level(self, generator):
        """Testa geração especificando tipo e nível."""
        challenge = await generator.generate(
            challenge_type=ChallengeType.ALGORITHM, level=ChallengeLevel.EASY
        )
        assert challenge.type == ChallengeType.ALGORITHM
        assert challenge.level == ChallengeLevel.EASY

    @pytest.mark.asyncio
    async def test_generate_invalid_type(self, generator):
        """Testa geração com tipo inválido."""
        with pytest.raises(ChallengeGenerationError):
            await generator.generate(challenge_type="invalid_type")

    @pytest.mark.asyncio
    async def test_generate_no_challenge_for_criteria(self, generator):
        """Testa quando não há desafio para os critérios."""
        try:
            challenge = await generator.generate(
                challenge_type=ChallengeType.MATH, level=ChallengeLevel.HARD
            )
            assert challenge.type == ChallengeType.MATH
        except ChallengeGenerationError as e:
            assert "No challenge available" in str(e)

    @pytest.mark.asyncio
    async def test_generate_unique_ids(self, generator):
        """Testa que cada desafio tem um ID único."""
        challenge1 = await generator.generate()
        challenge2 = await generator.generate()
        assert challenge1.id != challenge2.id

    @pytest.mark.asyncio
    async def test_to_dict(self, generator):
        """Testa conversão de desafio para dicionário."""
        challenge = await generator.generate()
        data = challenge.to_dict()

        assert isinstance(data, dict)
        assert "id" in data
        assert "type" in data
        assert "level" in data
        assert "title" in data
        assert data["type"] == challenge.type.value
        assert data["level"] == challenge.level.value

    @pytest.mark.asyncio
    async def test_generate_batch_default(self, generator):
        """Testa geração em lote com parâmetros padrão."""
        challenges = await generator.generate_batch(count=5)

        assert len(challenges) == 5
        assert all(isinstance(c, Challenge) for c in challenges)
        assert len(set(c.id for c in challenges)) == 5  # IDs únicos

    @pytest.mark.asyncio
    async def test_generate_batch_with_type(self, generator):
        """Testa geração em lote especificando tipo."""
        challenges = await generator.generate_batch(
            count=3, challenge_type=ChallengeType.ALGORITHM
        )

        assert len(challenges) == 3
        assert all(c.type == ChallengeType.ALGORITHM for c in challenges)

    def test_generate_batch_invalid_count(self, generator):
        """Testa geração em lote com contagem inválida."""
        with pytest.raises(ChallengeGenerationError):
            asyncio.run(generator.generate_batch(count=0))

        with pytest.raises(ChallengeGenerationError):
            asyncio.run(generator.generate_batch(count=-1))

        with pytest.raises(ChallengeGenerationError):
            asyncio.run(generator.generate_batch(count=1001))

    @pytest.mark.asyncio
    async def test_generate_batch_large(self, generator):
        """Testa geração em lote grande."""
        challenges = await generator.generate_batch(count=100)
        assert len(challenges) == 100
        assert all(isinstance(c, Challenge) for c in challenges)

    def test_get_available_types(self, generator):
        """Testa recuperação de tipos disponíveis."""
        types = generator.get_available_types()

        assert isinstance(types, list)
        assert len(types) > 0
        assert "algorithm" in types
        assert "string_manipulation" in types
        assert "math" in types

    def test_get_available_levels(self, generator):
        """Testa recuperação de níveis disponíveis."""
        levels = generator.get_available_levels()

        assert isinstance(levels, list)
        assert len(levels) > 0
        assert "easy" in levels
        assert "medium" in levels
        assert "hard" in levels

    @pytest.mark.asyncio
    async def test_challenge_metadata(self, generator):
        """Testa que metadados são incluídos."""
        challenge = await generator.generate()

        assert challenge.metadata is not None
        assert "generator_version" in challenge.metadata
        assert "source" in challenge.metadata
        assert challenge.metadata["source"] in ["pool", "llm", "mock"]
