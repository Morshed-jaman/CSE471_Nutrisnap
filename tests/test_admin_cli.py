from app.models import User


def test_create_admin_securely(app):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin", "--email", "owner@example.test", "--name", "Owner", "--phone", "+8801700000000"],
        input="A-strong-passphrase9!\nA-strong-passphrase9!\n",
    )
    assert result.exit_code == 0
    assert "A-strong-passphrase9!" not in result.output
    with app.app_context():
        admin = User.query.filter_by(email="owner@example.test").one()
        assert admin.role == "admin"
        assert admin.check_password("A-strong-passphrase9!")


def test_create_admin_rejects_weak_password(app):
    result = app.test_cli_runner().invoke(
        args=["create-admin", "--email", "owner@example.test", "--name", "Owner", "--phone", "+8801700000000"],
        input="weak\nweak\n",
    )
    assert result.exit_code != 0
    with app.app_context():
        assert User.query.filter_by(email="owner@example.test").count() == 0
