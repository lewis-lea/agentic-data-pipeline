"""Validate financial consistency and offline provenance of the public demo."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from agentic_data_pipeline import dashboard
from agentic_data_pipeline.synthetic import build_synthetic_snapshot, generate_histories, PROFILES
from agentic_data_pipeline.storage import ParquetStorage

ROOT = Path(__file__).parents[1]


def catalogue():
    return dashboard.load_catalogue(ROOT / 'config/ftse250-examples.json')


def test_reproducible_histories_and_seed_control():
    a, b, c = generate_histories(17), generate_histories(17), generate_histories(18)
    assert set(a) == set(PROFILES)
    for symbol in a:
        pd.testing.assert_frame_equal(a[symbol], b[symbol])
        assert not a[symbol].equals(c[symbol])
        assert len(a[symbol]) > 2500
        assert (a[symbol].index.dayofweek < 5).all()
        assert np.isfinite(a[symbol]).all().all()
        assert (a[symbol][['Close', 'Adj Close']] > 0).all().all()


def test_cash_reinvestment_and_correlated_shock():
    histories = generate_histories()
    for frame in histories.values():
        price, cash, adjusted = frame['Close'], frame['Dividends'], frame['Adj Close']
        np.testing.assert_allclose((price + cash).iloc[1:] / price.iloc[:-1].to_numpy(),
                                   adjusted.iloc[1:] / adjusted.iloc[:-1].to_numpy(), rtol=1e-12)
        assert adjusted.iloc[-1] == pytest.approx(price.iloc[-1])
        assert adjusted.iloc[-1] / adjusted.iloc[0] > price.iloc[-1] / price.iloc[0]
        assert (cash.loc['2019'] > 0).sum() == 2
        assert cash.loc['2020'].sum() == 0
        assert price.loc['2020-03-23'] / price.loc['2020-02-19'] < .85
    assert histories['SCT.L']['Close'].iloc[-1] > histories['SCT.L']['Close'].iloc[0]
    assert histories['CURY.L']['Close'].iloc[-1] < histories['CURY.L']['Close'].iloc[0]
    returns = pd.DataFrame({s: f['Adj Close'].pct_change() for s, f in histories.items()})
    assert returns.corr().to_numpy()[np.triu_indices(6, 1)].mean() > .05


def test_snapshot_offline_reproducibility_and_export_provenance(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError('Synthetic builds must never call Yahoo')
    monkeypatch.setattr(dashboard.yf, 'Ticker', no_network)
    first = build_synthetic_snapshot(catalogue())
    second = build_synthetic_snapshot(catalogue())
    assert first["instruments"] == second["instruments"]
    assert first["simulation"] == second["simulation"]
    assert first['synthetic'] is True
    assert all(i['synthetic'] and i['fetched_at'] is None for i in first['instruments'])
    dashboard.main(['--assets', str(ROOT / 'dashboard'), '--catalogue', str(ROOT / 'config/ftse250-examples.json'), '--output', str(tmp_path)])
    saved = json.loads((tmp_path / 'prices.json').read_text())
    assert saved['instruments'] == json.loads(json.dumps(first['instruments']))
    events = json.loads((tmp_path / 'corporate-actions.json').read_text())
    assert events['synthetic'] is True
    csv = pd.read_csv(tmp_path / 'corporate-actions.csv')
    assert csv['synthetic'].all() and (csv.data_source == 'synthetic').all()
    stored = ParquetStorage(tmp_path / 'datasets').load_dataset(source='synthetic', dataset='corporate_actions', symbol='GRG.L')
    assert stored.attrs['synthetic'] is True
    assert not (tmp_path / 'datasets/raw/yfinance').exists()
    assert 'Synthetic demonstration' in (tmp_path / 'index.html').read_text()


def test_unknown_profiles_and_real_cache_rejected(tmp_path):
    unknown = catalogue()
    unknown['instruments'][0]['symbol'] = 'UNKNOWN.L'
    with pytest.raises(ValueError, match='No synthetic profile'):
        build_synthetic_snapshot(unknown)
    with pytest.raises(SystemExit):
        dashboard.main(['--previous', str(tmp_path / 'prices.json')])
    snapshot = build_synthetic_snapshot(catalogue())
    (tmp_path / 'prices.json').write_text(json.dumps({'data_source': 'yfinance'}))
    with pytest.raises(ValueError, match='fresh output directory'):
        dashboard.write_site(snapshot, ROOT / 'dashboard', tmp_path)
    (tmp_path / 'prices.json').unlink()
    (tmp_path / 'datasets/raw/yfinance').mkdir(parents=True)
    with pytest.raises(ValueError, match='real-data exports'):
        dashboard.write_site(snapshot, ROOT / 'dashboard', tmp_path)
