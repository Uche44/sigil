"""Fixed test vectors. These lock the wire format; changing them is a protocol change."""

import pytest

from sigil.merkle import (
    MerkleError,
    MerkleTree,
    details_hash,
    leaf_hash,
    serial_leaves,
    verify_proof,
)

BATCH_PDA = bytes(range(32))
SERIALS = [bytes([i] * 10) for i in range(1, 4)]

LEAF_VECTOR = "b15a26fe4dfce5dd4f74b82dc924521f54a45475f19b2ffed42f7aabbd1f8a74"
ROOT_THREE = "18cbcf19f5c4dc4a9822f3da249be6c093cb9a471bd43c6611bedeb33e81357c"
ROOT_TWO = "5c99f5bab270010abb1bdf18a28cd0d1d71d84bcb2d7475db696034ca32170de"
DETAILS_VECTOR = "123f7f2a2c097a138cffcc6cc3819f5dd0cadd3c742d2f0b7ffe4886d29ac565"
DETAILS = {
    "product_name": "Paracetamol 500mg",
    "batch_number": "B-2026-001",
    "expiry_date": "2027-06-30",
}


def test_leaf_vector():
    assert leaf_hash(BATCH_PDA, SERIALS[0]).hex() == LEAF_VECTOR


def test_details_hash_vector():
    assert details_hash(DETAILS).hex() == DETAILS_VECTOR


def test_details_hash_ignores_key_order():
    reordered = dict(reversed(list(DETAILS.items())))
    assert details_hash(reordered) == details_hash(DETAILS)


def test_details_hash_changes_when_a_value_changes():
    changed = {**DETAILS, "batch_number": "B-2026-002"}
    assert details_hash(changed) != details_hash(DETAILS)


def test_three_leaf_root_vector():
    tree = MerkleTree.from_serials(BATCH_PDA, SERIALS)
    assert tree.root_hex == ROOT_THREE
    assert tree.leaf_count == 3


def test_odd_level_duplicates_last_node():
    # Two leaves and the same two leaves with the last duplicated must differ at
    # the leaf level but the three-leaf tree must equal tree over [l0, l1, l1].
    tree3 = MerkleTree.from_serials(BATCH_PDA, SERIALS)
    leaves = serial_leaves(BATCH_PDA, SERIALS)
    duplicated = MerkleTree([leaves[0], leaves[1], leaves[2], leaves[2]])
    assert tree3.root == duplicated.root


def test_two_leaf_root_vector():
    assert MerkleTree.from_serials(BATCH_PDA, SERIALS[:2]).root_hex == ROOT_TWO


def test_every_proof_verifies():
    tree = MerkleTree.from_serials(BATCH_PDA, SERIALS)
    for index, leaf in enumerate(tree.leaves):
        proof = tree.proof(index)
        assert verify_proof(leaf, proof, tree.root)


def test_proofs_verify_for_a_large_odd_tree():
    serials = [bytes([i % 256, (i // 256) % 256]) * 5 for i in range(101)]
    tree = MerkleTree.from_serials(BATCH_PDA, serials)
    for index in [0, 1, 50, 99, 100]:
        assert verify_proof(tree.leaves[index], tree.proof(index), tree.root)


def test_wrong_leaf_fails():
    tree = MerkleTree.from_serials(BATCH_PDA, SERIALS)
    other = leaf_hash(BATCH_PDA, bytes([99] * 10))
    assert not verify_proof(other, tree.proof(1), tree.root)


def test_tampered_proof_fails():
    tree = MerkleTree.from_serials(BATCH_PDA, SERIALS)
    proof = tree.proof(0)
    bad = list(proof)
    bad[0] = type(proof[0])(sibling=bytes([0] * 32), left=proof[0].left)
    assert not verify_proof(tree.leaves[0], bad, tree.root)


def test_leaf_depends_on_batch_pda():
    other_pda = bytes([255] * 32)
    assert leaf_hash(BATCH_PDA, SERIALS[0]) != leaf_hash(other_pda, SERIALS[0])


def test_proof_round_trips_through_json():
    tree = MerkleTree.from_serials(BATCH_PDA, SERIALS)
    proof = [step.to_json() for step in tree.proof(2)]
    restored = [type(tree.proof(2)[0]).from_json(step) for step in proof]
    assert verify_proof(tree.leaves[2], restored, tree.root)


def test_empty_tree_is_rejected():
    with pytest.raises(MerkleError):
        MerkleTree([])


def test_out_of_range_proof_is_rejected():
    tree = MerkleTree.from_serials(BATCH_PDA, SERIALS)
    with pytest.raises(MerkleError):
        tree.proof(3)
