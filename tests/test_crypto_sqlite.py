from unittest import mock

import pytest

from sqliteplus.utils.crypto_sqlite import verify_cipher_support
from sqliteplus.utils.sqliteplus_sync import SQLitePlusCipherError, apply_cipher_key


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


def test_apply_cipher_key_skips_blank_key_without_encryption_requirement():
    connection = mock.Mock()

    apply_cipher_key(connection, "   ")

    connection.execute.assert_not_called()


def test_apply_cipher_key_rejects_blank_key_when_encryption_required():
    connection = mock.Mock()

    with pytest.raises(SQLitePlusCipherError):
        verify_cipher_support(
            cipher_key="   ",
            cipher_version_row=("4.5.1",),
            exception_factory=lambda message: SQLitePlusCipherError(message=message),
        )

    connection.execute.assert_not_called()
