import pytest
import unittest

from deepdiff import DeepDiff

from api.jobs.queue import Queue

# Map request keys to DB keys
groupK = "group"
groupD = "parents.group"
gearNameK = "gear-name"
gearNameD = "gear_info.name"
tagK = "tag"
tagD = "tags"

# Mongo query keys
Ycontains = "$in"
Ncontains = "$nin"

# Example keys
A = "Almond"
B = "Black"
C = "Charcoal"
D = "Denim"
E = "Electric"
F = "Folly"


class QueueTestCases(unittest.TestCase):
    def deep_equal(self, result, expected):
        """
        This could move into a type hierarchy; needs to be downstream from TestCase.

        https://github.com/seperman/deepdiff#using-deepdiff-in-unit-tests
        """

        diff = DeepDiff(result, expected)

        if diff != {}:
            print("Result:   " + str(result))
            print("Expected: " + str(expected))
            # print('Diff:     ' + str(diff))

        self.assertEqual(DeepDiff(result, expected), {})

    def test_queue_lists_to_query(self):

        # Whitelist, blacklist, and expected result
        matrix = [
            [
                # Empty lists should match all jobs
                {},
                {},
                {},
            ],
            [
                # Whitelisting a group
                {groupK: [A]},
                {},
                {groupD: {Ycontains: [A]}},
            ],
            [
                # Blacklisting a group
                {},
                {groupK: [A]},
                {groupD: {Ncontains: [A]}},
            ],
            [
                # Both groups
                {groupK: [A]},
                {groupK: [B]},
                {groupD: {Ycontains: [A], Ncontains: [B]}},
            ],
            [
                # Whitelisting a gear name
                {gearNameK: [A]},
                {},
                {gearNameD: {Ycontains: [A]}},
            ],
            [
                # Blacklisting a gear name
                {},
                {gearNameK: [A]},
                {gearNameD: {Ncontains: [A]}},
            ],
            [
                # Both gearNames
                {gearNameK: [A]},
                {gearNameK: [B]},
                {gearNameD: {Ycontains: [A], Ncontains: [B]}},
            ],
            [
                # Whitelisting a tag
                {tagK: [A]},
                {},
                {tagD: {Ycontains: [A]}},
            ],
            [
                # Blacklisting a tag
                {},
                {tagK: [A]},
                {tagD: {Ncontains: [A]}},
            ],
            [
                # Both tags
                {tagK: [A]},
                {tagK: [B]},
                {tagD: {Ycontains: [A], Ncontains: [B]}},
            ],
            [
                # Overlapping tags - nonsensical, but relied upon for legacy endpoints.
                {tagK: [A]},
                {tagK: [A]},
                {tagD: {Ycontains: [A], Ncontains: [A]}},
            ],
            [
                # Combine all filters
                {groupK: [A], gearNameK: [C], tagK: [E]},
                {groupK: [B], gearNameK: [D], tagK: [F]},
                {groupD: {Ycontains: [A], Ncontains: [B]}, gearNameD: {Ycontains: [C], Ncontains: [D]}, tagD: {Ycontains: [E], Ncontains: [F]}},
            ],
        ]

        for case in matrix:
            assert len(case) == 3

            whitelist = case[0]
            blacklist = case[1]
            expected = case[2]
            capabilities = []

            result = Queue.lists_to_query(whitelist, blacklist, capabilities)
            del result["gear_info.capabilities"]
            self.deep_equal(result, expected)
