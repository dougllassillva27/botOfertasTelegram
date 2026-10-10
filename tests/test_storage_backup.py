"""
Testes unitários para o backup automático do storage.
Cobre: backup datado antes da escrita, retenção limitada, primeiro save.
"""

import json

from app import storage


class TestAutoBackup:
    """Testes para o backup automático pré-escrita do data.json."""

    def _read(self, path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_backup_created_before_overwrite(self, tmp_path, monkeypatch):
        """Sobrescrever deve gerar um backup datado do conteúdo anterior."""
        data_file = tmp_path / "data.json"
        monkeypatch.setattr(storage, "DATA_FILE", str(data_file))
        data_file.write_text(
            json.dumps({"grupos": ["original"], "alertas": []}), encoding="utf-8"
        )

        storage.save_data({"grupos": ["novo"], "alertas": []})

        backups = list(tmp_path.glob("data.json.bak-*"))
        assert len(backups) == 1
        assert self._read(backups[0])["grupos"] == ["original"]

    def test_backup_not_created_when_no_previous_file(self, tmp_path, monkeypatch):
        """Primeiro save (sem arquivo anterior) não gera backup."""
        monkeypatch.setattr(storage, "DATA_FILE", str(tmp_path / "data.json"))
        storage.save_data({"grupos": ["a"], "alertas": []})
        assert list(tmp_path.glob("data.json.bak-*")) == []

    def test_current_file_is_written(self, tmp_path, monkeypatch):
        """O data.json atual deve receber o novo estado."""
        monkeypatch.setattr(storage, "DATA_FILE", str(tmp_path / "data.json"))
        storage.save_data({"grupos": ["x"], "alertas": []})
        assert self._read(tmp_path / "data.json")["grupos"] == ["x"]

    def test_backups_are_pruned(self, tmp_path, monkeypatch):
        """Acima do limite, os backups mais antigos são removidos."""
        data_file = tmp_path / "data.json"
        monkeypatch.setattr(storage, "DATA_FILE", str(data_file))

        for i in range(storage.BACKUP_KEEP + 5):
            data_file.write_text(
                json.dumps({"grupos": [f"g{i}"], "alertas": []}), encoding="utf-8"
            )
            storage.save_data({"grupos": [f"novo{i}"], "alertas": []})

        assert len(list(tmp_path.glob("data.json.bak-*"))) == storage.BACKUP_KEEP

    def test_backup_contents_match_pre_write_state(self, tmp_path, monkeypatch):
        """Cada backup reflete o estado ANTES daquela escrita específica."""
        data_file = tmp_path / "data.json"
        monkeypatch.setattr(storage, "DATA_FILE", str(data_file))
        data_file.write_text(
            json.dumps({"grupos": ["v1"], "alertas": []}), encoding="utf-8"
        )
        storage.save_data({"grupos": ["v2"], "alertas": []})
        storage.save_data({"grupos": ["v3"], "alertas": []})

        backups = sorted(tmp_path.glob("data.json.bak-*"))
        conteudos = [self._read(b)["grupos"][0] for b in backups]
        assert "v1" in conteudos
        assert "v2" in conteudos
