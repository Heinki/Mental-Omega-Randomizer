"""Crash-serializable Archipelago item receipt ledger."""

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

from .handshake import ArchipelagoProtocolError


@dataclass(frozen=True)
class ReceivedItem:
    index: int
    item: int
    location: int
    player: int
    flags: int

    @classmethod
    def from_network(cls, index, value):
        if not isinstance(value, Mapping):
            raise ArchipelagoProtocolError('ReceivedItems entry is invalid.')
        try:
            fields = {
                key: int(value[key])
                for key in ('item', 'location', 'player', 'flags')
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ArchipelagoProtocolError(
                'ReceivedItems entry is missing numeric fields.'
            ) from exc
        return cls(index=int(index), **fields)

    @classmethod
    def from_checkpoint(cls, value):
        if not isinstance(value, Mapping):
            raise ValueError('Saved Archipelago item entry is invalid.')
        try:
            return cls(**{
                key: int(value[key])
                for key in ('index', 'item', 'location', 'player', 'flags')
            })
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Saved Archipelago item entry is invalid.') from exc

    def to_dict(self):
        return asdict(self)


class ReceivedItemLedger:
    """Track network receipts and durable reward-application acknowledgments."""

    def __init__(self, records=(), acknowledged_indexes=()):
        self._records = {}
        for record in records:
            if not isinstance(record, ReceivedItem):
                raise TypeError('Ledger records must be ReceivedItem values.')
            if record.index < 0 or record.index in self._records:
                raise ValueError('Ledger item indexes must be unique and nonnegative.')
            self._records[record.index] = record
        self._acknowledged = {
            int(index)
            for index in acknowledged_indexes
            if int(index) in self._records
        }

    @classmethod
    def from_checkpoint(cls, value):
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise ValueError('Saved Archipelago ledger must be an object.')
        records = [
            ReceivedItem.from_checkpoint(record)
            for record in value.get('received_items', [])
        ]
        acknowledged = value.get('acknowledged_item_indexes', [])
        if not isinstance(acknowledged, list):
            raise ValueError('Saved acknowledged item indexes must be a list.')
        return cls(records, acknowledged)

    @property
    def next_index(self):
        index = 0
        while index in self._records:
            index += 1
        return index

    @property
    def records(self):
        return tuple(self._records[index] for index in sorted(self._records))

    @property
    def pending(self):
        return tuple(
            self._records[index]
            for index in sorted(self._records)
            if index not in self._acknowledged
        )

    @property
    def acknowledged_indexes(self):
        return tuple(sorted(self._acknowledged))

    def ingest(self, start_index, items):
        """Accept one ReceivedItems packet and report pending receipts plus gaps."""
        try:
            start_index = int(start_index)
        except (TypeError, ValueError) as exc:
            raise ArchipelagoProtocolError(
                'ReceivedItems index is invalid.'
            ) from exc
        if start_index < 0 or not isinstance(items, Sequence):
            raise ArchipelagoProtocolError('ReceivedItems packet is invalid.')

        expected_index = self.next_index
        desynchronized = start_index not in {0, expected_index}
        incoming = {
            start_index + offset: ReceivedItem.from_network(
                start_index + offset, item
            )
            for offset, item in enumerate(items)
        }

        if start_index == 0:
            old_records = self._records
            old_acknowledged = self._acknowledged
            self._records = incoming
            self._acknowledged = {
                index
                for index in old_acknowledged
                if old_records.get(index) == incoming.get(index)
            }
        else:
            for index, record in incoming.items():
                if self._records.get(index) != record:
                    self._records[index] = record
                    self._acknowledged.discard(index)

        pending = tuple(
            self._records[index]
            for index in sorted(incoming)
            if index in self._records and index not in self._acknowledged
        )
        return pending, desynchronized

    def acknowledge(self, indexes):
        changed = False
        for index in indexes:
            index = int(index)
            if index in self._records and index not in self._acknowledged:
                self._acknowledged.add(index)
                changed = True
        return changed

    def to_checkpoint(self):
        return {
            'received_item_index': self.next_index,
            'received_items': [record.to_dict() for record in self.records],
            'acknowledged_item_indexes': list(self.acknowledged_indexes),
        }
