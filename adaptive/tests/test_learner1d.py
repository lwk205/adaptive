# -*- coding: utf-8 -*-

import random
import numpy as np

from ..learner import Learner1D
from ..learner.learner1D import get_curvature_loss
from ..runner import simple


def test_pending_loss_intervals():
    # https://gitlab.kwant-project.org/qt/adaptive/issues/99
    l = Learner1D(lambda x: x, (0, 4))

    l.tell(0, 0)
    l.tell(1, 0)
    l.tell(2, 0)
    assert set(l.losses_combined.keys()) == {(0, 1), (1, 2)}
    l.ask(1)
    assert set(l.losses_combined.keys()) == {(0, 1), (1, 2), (2, 4)}
    l.tell(3.5, 0)
    assert set(l.losses_combined.keys()) == {
        (0, 1), (1, 2), (2, 3.5), (3.5, 4.0)}


def test_loss_interpolation_for_unasked_point():
    # https://gitlab.kwant-project.org/qt/adaptive/issues/99
    l = Learner1D(lambda x: x, (0, 4))

    l.tell(0, 0)
    l.tell(1, 0)
    l.tell(2, 0)

    assert l.ask(1) == ([4], [np.inf])
    assert l.losses == {(0, 1): 0.25, (1, 2): 0.25}
    assert l.losses_combined == {(0, 1): 0.25, (1, 2): 0.25, (2, 4.0): np.inf}

    # assert l.ask(1) == ([3], [np.inf])  # XXX: This doesn't return np.inf as loss_improvement...
    l.ask(1)
    assert l.losses == {(0, 1): 0.25, (1, 2): 0.25}
    assert l.losses_combined == {
        (0, 1): 0.25, (1, 2): 0.25, (2, 3.0): np.inf, (3.0, 4.0): np.inf}

    l.tell(4, 0)

    assert l.losses_combined == {
        (0, 1): 0.25, (1, 2): 0.25, (2, 3): 0.25, (3, 4): 0.25}


def test_first_iteration():
    """Edge cases where we ask for a few points at the start."""
    learner = Learner1D(lambda x: None, (-1, 1))
    points, loss_improvements = learner.ask(2)
    assert set(points) == set(learner.bounds)

    learner = Learner1D(lambda x: None, (-1, 1))
    points, loss_improvements = learner.ask(3)
    assert set(points) == set([-1, 0, 1])

    learner = Learner1D(lambda x: None, (-1, 1))
    points, loss_improvements = learner.ask(1)
    assert len(points) == 1 and points[0] in learner.bounds
    rest = set([-1, 0, 1]) - set(points)
    points, loss_improvements = learner.ask(2)
    assert set(points) == set(rest)

    learner = Learner1D(lambda x: None, (-1, 1))
    points, loss_improvements = learner.ask(1)
    to_see = set(learner.bounds) - set(points)
    points, loss_improvements = learner.ask(1)
    assert set(points) == set(to_see)

    learner = Learner1D(lambda x: None, (-1, 1))
    learner.tell(1, 0)
    points, loss_improvements = learner.ask(1)
    assert points == [-1]

    learner = Learner1D(lambda x: None, (-1, 1))
    learner.tell(-1, 0)
    points, loss_improvements = learner.ask(1)
    assert points == [1]


def test_loss_interpolation():
    learner = Learner1D(lambda _: 0, bounds=(-1, 1))

    learner.tell(-1, 0)
    learner.tell(1, 0)
    for i in range(100):
        # Add a 100 points with either None or 0
        if random.random() < 0.9:
            learner.tell(random.uniform(-1, 1), None)
        else:
            learner.tell(random.uniform(-1, 1), 0)

    for (x1, x2), loss in learner.losses_combined.items():
        expected_loss = (x2 - x1) / 2
        assert abs(expected_loss - loss) < 1e-15, (expected_loss, loss)


def _run_on_discontinuity(x_0, bounds):

    def f(x):
        return -1 if x < x_0 else +1

    learner = Learner1D(f, bounds)
    while learner.loss() > 0.1:
        (x,), _ = learner.ask(1)
        learner.tell(x, learner.function(x))

    return learner


def test_termination_on_discontinuities():

    learner = _run_on_discontinuity(0, (-1, 1))
    smallest_interval = min(abs(a - b) for a, b in learner.losses.keys())
    assert smallest_interval >= np.finfo(float).eps

    learner = _run_on_discontinuity(1, (-2, 2))
    smallest_interval = min(abs(a - b) for a, b in learner.losses.keys())
    assert smallest_interval >= np.finfo(float).eps

    learner = _run_on_discontinuity(0.5e3, (-1e3, 1e3))
    smallest_interval = min(abs(a - b) for a, b in learner.losses.keys())
    assert smallest_interval >= 0.5e3 * np.finfo(float).eps


def test_order_adding_points():
    # and https://gitlab.kwant-project.org/qt/adaptive/issues/98
    l = Learner1D(lambda x: x, (0, 1))
    l.tell_many([1, 0, 0.5], [0, 0, 0])
    assert l.losses_combined == {(0, 0.5): 0.5, (0.5, 1): 0.5}
    assert l.losses == {(0, 0.5): 0.5, (0.5, 1): 0.5}
    l.ask(1)


def test_adding_existing_point_passes_silently():
    # See https://gitlab.kwant-project.org/qt/adaptive/issues/97
    l = Learner1D(lambda x: x, (0, 4))
    l.tell(0, 0)
    l.tell(1, 0)
    l.tell(2, 0)
    l.tell(1, None)


def test_loss_at_machine_precision_interval_is_zero():
    """The loss of an interval smaller than _dx_eps
    should be set to zero."""
    def f(x):
        return 1 if x == 0 else 0

    def goal(l):
        return l.loss() < 0.01 or l.npoints >= 1000

    learner = Learner1D(f, bounds=(-1, 1))
    simple(learner, goal=goal)

    # this means loss < 0.01 was reached
    assert learner.npoints != 1000


def small_deviations(x):
    return 0 if x <= 1 else 1 + 10**(-random.randint(12, 14))


def test_small_deviations():
    """This tests whether the Learner1D can handle small deviations.
    See https://gitlab.kwant-project.org/qt/adaptive/merge_requests/73 and
    https://gitlab.kwant-project.org/qt/adaptive/issues/61."""

    eps = 5e-14
    learner = Learner1D(small_deviations, bounds=(1 - eps, 1 + eps))

    # Some non-determinism is needed to make this test fail so we keep
    # a list of points that will be evaluated later to emulate
    # parallel execution
    stash = []

    for i in range(100):
        xs, _ = learner.ask(10)

        # Save 5 random points out of `xs` for later
        random.shuffle(xs)
        for _ in range(5):
            stash.append(xs.pop())

        for x in xs:
            learner.tell(x, learner.function(x))

        # Evaluate and add 5 random points from `stash`
        random.shuffle(stash)
        for _ in range(5):
            learner.tell(stash.pop(), learner.function(x))

        if learner.loss() == 0:
            # If this condition is met, the learner can't return any
            # more points.
            break


def test_uniform_sampling1D_v2():
    def check(known, expect):
        def f(x):
            return x
        learner = Learner1D(f, bounds=(-1, 1))
        for x in known:
            learner.tell(x, f(x))
        pts, _ = learner.ask(len(expect))
        assert set(pts) == expect

    check([-1, 0, 1], {-0.5, 0.5})
    check([-1, -0.5, 1], {0, 0.5})
    check([-1, 0.5, 1], {-0.5, 0})
    check([-1, 0], {1})
    # although the following test might be unexpected, this is indeed correct
    # given the default loss function
    check([-1, 0], {-.5, 1})
    check([-1, -.5], {-.75, 1})
    check([-1, -.5], {-.75, .25, 1})


def test_add_data_unordered():
    # see https://gitlab.kwant-project.org/qt/adaptive/issues/95
    learner = Learner1D(lambda x: x, bounds=(-1, 1))
    xs = [-1, 1, 0]

    ys = [learner.function(x) for x in xs]
    for x, y in zip(xs, ys):
        learner.tell(x, y)

    learner.ask(3)


def test_ask_does_not_return_known_points_when_returning_bounds():
    learner = Learner1D(lambda x: None, (-1, 1))
    learner.tell(0, 0)
    points, _ = learner.ask(3)
    assert 0 not in points


def test_tell_many():
    def f(x, offset=0.123214):
        a = 0.01
        return (np.sin(x**2) + np.sin(x**5)
                + a**2 / (a**2 + (x - offset)**2)
                + x**2 + 1e-5 * x**3)

    def f_vec(x, offset=0.123214):
        a = 0.01
        y = x + a**2 / (a**2 + (x - offset)**2)
        return [y, 0.5 * y, y**2]

    def assert_equal_dicts(d1, d2):
        xs1, ys1 = zip(*sorted(d1.items()))
        xs2, ys2 = zip(*sorted(d2.items()))
        ys1 = np.array(ys1, dtype=np.float)
        ys2 = np.array(ys2, dtype=np.float)
        np.testing.assert_almost_equal(xs1, xs2)
        np.testing.assert_almost_equal(ys1, ys2)

    def test_equal(l1, l2):
        assert_equal_dicts(l1.neighbors, l2.neighbors)
        assert_equal_dicts(l1.neighbors_combined, l2.neighbors_combined)
        assert_equal_dicts(l1.data, l2.data)
        assert_equal_dicts(l2.losses, l1.losses)
        assert_equal_dicts(l2.losses_combined, l1.losses_combined)
        np.testing.assert_almost_equal(sorted(l1.pending_points),
                                       sorted(l2.pending_points))
        np.testing.assert_almost_equal(l1._bbox[1], l1._bbox[1])
        assert l1._scale == l2._scale
        assert l1._bbox[0] == l2._bbox[0]

    for function in [f, f_vec]:
        learner = Learner1D(function, bounds=(-1, 1))
        learner2 = Learner1D(function, bounds=(-1, 1))
        simple(learner, goal=lambda l: l.npoints > 200)
        xs, ys = zip(*learner.data.items())

        # Make the scale huge to no get a scale doubling
        x = 1e-6
        max_value = 1e6 if learner.vdim == 1 else np.array(learner.vdim * [1e6])
        learner.tell(x, max_value)
        learner2.tell(x, max_value)

        for x in xs:
            learner2.tell_pending(x)

        learner2.tell_many(xs, ys)
        test_equal(learner, learner2)

    # Test non-determinism. We keep a list of points that will be
    # evaluated later to emulate parallel execution.
    def _random_run(learner, learner2, scale_doubling=True):
        if not scale_doubling:
            # Make the scale huge to no get a scale doubling
            x = 1e-6
            max_value = 1e6
            learner.tell(x, max_value)
            learner2.tell(x, max_value)

        stash = []
        for i in range(10):
            xs, _ = learner.ask(10)
            for x in xs:
                learner2.tell_pending(x)

            # Save 5 random points out of `xs` for later
            random.shuffle(xs)
            for _ in range(5):
                stash.append(xs.pop())

            ys = [learner.function(x) for x in xs]

            learner.tell_many(xs, ys, force=True)
            for x, y in zip(xs, ys):
                learner2.tell(x, y)

            # Evaluate and add N random points from `stash`
            random.shuffle(stash)
            xs = [stash.pop() for _ in range(random.randint(1, 5))]
            ys = [learner.function(x) for x in xs]

            learner.tell_many(xs, ys, force=True)
            for x, y in zip(xs, ys):
                learner2.tell(x, y)

        if scale_doubling:
            # Double the scale to trigger the loss updates
            max_value = max(learner.data.values())
            x = 1e-6
            learner.tell(x, max_value * 10)
            learner2.tell(x, max_value * 10)

    learner = Learner1D(f, bounds=(-1, 1))
    learner2 = Learner1D(f, bounds=(-1, 1))
    _random_run(learner, learner2, scale_doubling=False)
    test_equal(learner, learner2)

    learner = Learner1D(f, bounds=(-1, 1))
    learner2 = Learner1D(f, bounds=(-1, 1))
    _random_run(learner, learner2, scale_doubling=True)
    test_equal(learner, learner2)


def test_curvature_loss():
    def f(x):
        return np.tanh(20*x)

    learner = Learner1D(f, (-1, 1), loss_per_interval=get_curvature_loss(), loss_depends_on_neighbours=True)
    simple(learner, goal=lambda l: l.npoints > 100)
    # assert this is reached without error


def test_curvature_loss_vectors():
    def f(x):
        return np.tanh(20*x), np.tanh(20*(x-0.4))

    learner = Learner1D(f, (-1, 1), loss_per_interval=get_curvature_loss(), loss_depends_on_neighbours=True)
    simple(learner, goal=lambda l: l.npoints > 100)
    assert learner.npoints > 100
