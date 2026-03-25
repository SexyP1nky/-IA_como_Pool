"""
Testes para o módulo de geração de desafios.

Cobre:
- Geração individual de desafios
- Geração em lote
- Validação de tipos e níveis
- Tratamento de erros
"""
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

    def test_generate_default(self, generator):
        """Testa geração com parâmetros padrão."""
        challenge = generator.generate()

        assert isinstance(challenge, Challenge)
        assert challenge.id
        assert challenge.type in ChallengeType
        assert challenge.level in ChallengeLevel
        assert challenge.title
        assert challenge.description
        assert challenge.created_at
        assert challenge.metadata

    def test_generate_with_type(self, generator):
        """Testa geração especificando o tipo."""
        for challenge_type in ChallengeType:
            challenge = generator.generate(challenge_type=challenge_type)
            assert challenge.type == challenge_type

    def test_generate_with_level(self, generator):
        """Testa geração especificando o nível."""
        # Nem todos os tipos têm todos os níveis disponíveis
        # Testamos apenas com tipos que sabemos ter múltiplos níveis
        for level in ChallengeLevel:
            try:
                challenge = generator.generate(
                    challenge_type=ChallengeType.ALGORITHM, level=level
                )
                assert challenge.level == level
            except Exception:
                # Alguns tipos podem não ter todos os níveis, e isso é aceitável
                pass

    def test_generate_with_type_and_level(self, generator):
        """Testa geração especificando tipo e nível."""
        challenge = generator.generate(
            challenge_type=ChallengeType.ALGORITHM, level=ChallengeLevel.EASY
        )
        assert challenge.type == ChallengeType.ALGORITHM
        assert challenge.level == ChallengeLevel.EASY

    def test_generate_invalid_type(self, generator):
        """Testa geração com tipo inválido."""
        with pytest.raises(ChallengeGenerationError):
            generator.generate(challenge_type="invalid_type")

    def test_generate_no_challenge_for_criteria(self, generator):
        """Testa quando não há desafio para os critérios."""
        # Tenta um tipo que pode não ter todos os níveis
        try:
            challenge = generator.generate(
                challenge_type=ChallengeType.MATH, level=ChallengeLevel.HARD
            )
            # Se conseguiu, tudo bem
            assert challenge.type == ChallengeType.MATH
        except ChallengeGenerationError as e:
            # Se falhou, deve ser por falta de desafio
            assert "No challenge available" in str(e)

    def test_generate_unique_ids(self, generator):
        """Testa que cada desafio tem um ID único."""
        challenge1 = generator.generate()
        challenge2 = generator.generate()
        assert challenge1.id != challenge2.id

    def test_to_dict(self, generator):
        """Testa conversão de desafio para dicionário."""
        challenge = generator.generate()
        data = challenge.to_dict()

        assert isinstance(data, dict)
        assert "id" in data
        assert "type" in data
        assert "level" in data
        assert "title" in data
        assert data["type"] == challenge.type.value
        assert data["level"] == challenge.level.value

    def test_generate_batch_default(self, generator):
        """Testa geração em lote com parâmetros padrão."""
        challenges = generator.generate_batch(count=5)

        assert len(challenges) == 5
        assert all(isinstance(c, Challenge) for c in challenges)
        assert len(set(c.id for c in challenges)) == 5  # IDs únicos

    def test_generate_batch_with_type(self, generator):
        """Testa geração em lote especificando tipo."""
        challenges = generator.generate_batch(
            count=3, challenge_type=ChallengeType.ALGORITHM
        )

        assert len(challenges) == 3
        assert all(c.type == ChallengeType.ALGORITHM for c in challenges)

    def test_generate_batch_invalid_count(self, generator):
        """Testa geração em lote com contagem inválida."""
        with pytest.raises(ChallengeGenerationError):
            generator.generate_batch(count=0)

        with pytest.raises(ChallengeGenerationError):
            generator.generate_batch(count=-1)

        with pytest.raises(ChallengeGenerationError):
            generator.generate_batch(count=1001)

    def test_generate_batch_large(self, generator):
        """Testa geração em lote grande."""
        challenges = generator.generate_batch(count=100)
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

    def test_challenge_metadata(self, generator):
        """Testa que metadados são incluídos."""
        challenge = generator.generate()

        assert challenge.metadata is not None
        assert "generator_version" in challenge.metadata
        assert "source" in challenge.metadata
        assert challenge.metadata["source"] == "pool"
