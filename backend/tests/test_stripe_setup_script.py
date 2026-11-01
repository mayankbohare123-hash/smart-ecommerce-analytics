"""The Stripe bootstrap script must be idempotent and refuse live keys by default."""
from types import SimpleNamespace
from unittest.mock import patch

from scripts import setup_stripe


def test_refuses_live_key_without_flag(monkeypatch, capsys):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_abc")
    with patch("stripe.Price.create") as create:
        assert setup_stripe.main([]) == 1
    create.assert_not_called()
    assert "LIVE" in capsys.readouterr().out


def test_missing_key_is_reported(monkeypatch, capsys):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with patch("scripts.setup_stripe.load_dotenv"):
        assert setup_stripe.main([]) == 1
    assert "STRIPE_SECRET_KEY" in capsys.readouterr().out


def test_creates_both_prices_with_correct_amounts(monkeypatch, capsys):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    prices = iter(["price_S", "price_P"])
    with patch("stripe.Price.list", return_value=SimpleNamespace(data=[])), \
         patch("stripe.Product.create", return_value=SimpleNamespace(id="prod_1")), \
         patch("stripe.Price.create", side_effect=lambda **kw: SimpleNamespace(id=next(prices))) as create:
        assert setup_stripe.main([]) == 0
    amounts = [c.kwargs["unit_amount"] for c in create.call_args_list]
    assert amounts == [1900, 4900]
    assert all(c.kwargs["recurring"] == {"interval": "month"} for c in create.call_args_list)
    out = capsys.readouterr().out
    assert "STRIPE_STARTER_PRICE_ID=price_S" in out and "STRIPE_PRO_PRICE_ID=price_P" in out


def test_is_idempotent_when_prices_exist(monkeypatch, capsys):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    with patch("stripe.Price.list", return_value=SimpleNamespace(data=[SimpleNamespace(id="price_existing")])), \
         patch("stripe.Product.create") as product, patch("stripe.Price.create") as create:
        assert setup_stripe.main([]) == 0
    product.assert_not_called(); create.assert_not_called()
    assert "price_existing" in capsys.readouterr().out
