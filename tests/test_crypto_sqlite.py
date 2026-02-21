import pytest

from sqliteplus.utils.crypto_sqlite import verify_cipher_support


def _factory(message: str) -> RuntimeError:
    return RuntimeError(message)


def test_verify_cipher_support_with_capability_present():
    verify_cipher_support(
        cipher_key="secret",
        cipher_version_row=("4.5.1",),
        exception_factory=_factory,
    )


def test_verify_cipher_support_without_capability_raises():
    with pytest.raises(RuntimeError):
        verify_cipher_support(
            cipher_key="secret",
            cipher_version_row=("",),
            exception_factory=_factory,
        )


def test_verify_cipher_support_with_empty_or_malformed_key_raises():
    with pytest.raises(RuntimeError):
        verify_cipher_support(
            cipher_key="   ",
            cipher_version_row=("4.5.1",),
            exception_factory=_factory,
        )

    with pytest.raises(RuntimeError):
        verify_cipher_support(
            cipher_key=None,
            cipher_version_row=("4.5.1",),
            exception_factory=_factory,
        )
