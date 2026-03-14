"""
Compute grid size (units) and even padding from target dimensions (drawer or print plate).
Single source of truth for "drawer/print plate -> grid + padding" logic.
All dimensions use the same length units (document units).
"""


def compute_grid_and_padding_from_drawer(
    drawer_width: float,
    drawer_length: float,
    base_width: float,
    base_length: float,
    xy_clearance: float,
):
    """
    Given target dimensions (e.g. drawer or print plate), compute the maximum
    grid size in units and even padding on all four sides so grid + padding fills the target.

    Args:
        drawer_width: Target width (same units as base_width).
        drawer_length: Target length (same units as base_length).
        base_width: Width of one grid unit (e.g. 4.2 for 42 mm).
        base_length: Length of one grid unit (e.g. 4.2 for 42 mm).
        xy_clearance: Bin xy clearance (same units).

    Returns:
        Tuple of (plate_width_u, plate_length_u, padding_left, padding_top, padding_right, padding_bottom).
        Padding is evenly distributed: left=right, top=bottom.
    """
    plate_width_u = max(1, int((drawer_width + 2 * xy_clearance) / base_width))
    plate_length_u = max(1, int((drawer_length + 2 * xy_clearance) / base_length))

    grid_width = plate_width_u * base_width - 2 * xy_clearance
    grid_length = plate_length_u * base_length - 2 * xy_clearance

    padding_x = max(0.0, (drawer_width - grid_width) / 2)
    padding_y = max(0.0, (drawer_length - grid_length) / 2)

    padding_left = padding_right = padding_x
    padding_top = padding_bottom = padding_y

    return (
        plate_width_u,
        plate_length_u,
        padding_left,
        padding_top,
        padding_right,
        padding_bottom,
    )


def _split_even(total: int, n: int) -> list:
    """Split total into n chunks as even as possible (e.g. 10 into 2 -> [5,5], 10 into 3 -> [4,3,3])."""
    if n <= 0:
        return []
    if n >= total:
        return [1] * total + [0] * (n - total)
    base = total // n
    remainder = total % n
    return [base + 1] * remainder + [base] * (n - remainder)


def compute_plate_split(
    total_w_u: int,
    total_l_u: int,
    print_w_cm: float,
    print_l_cm: float,
    base_width: float,
    base_length: float,
    xy_clearance: float,
):
    """
    Determine how to split a full grid (total_w_u x total_l_u) into multiple plates that each
    fit on the print bed (print_w_cm x print_l_cm). All lengths in cm.

    Returns:
        Tuple (num_x, num_y, chunk_widths, chunk_lengths) where:
        - num_x, num_y: number of plates in X and Y.
        - chunk_widths: list of width in grid units for each column (length num_x).
        - chunk_lengths: list of length in grid units for each row (length num_y).
        If the full grid fits on one plate, returns (1, 1, [total_w_u], [total_l_u]).
    """
    if print_w_cm <= 0 or print_l_cm <= 0:
        return (1, 1, [total_w_u], [total_l_u])

    # Max grid units that fit on one plate (physical size = u * base - 2*xy_clearance <= print)
    max_w_u = max(1, int((print_w_cm + 2 * xy_clearance) / base_width))
    max_l_u = max(1, int((print_l_cm + 2 * xy_clearance) / base_length))

    if total_w_u <= max_w_u and total_l_u <= max_l_u:
        return (1, 1, [total_w_u], [total_l_u])

    num_x = (total_w_u + max_w_u - 1) // max_w_u
    num_y = (total_l_u + max_l_u - 1) // max_l_u
    chunk_widths = _split_even(total_w_u, num_x)
    chunk_lengths = _split_even(total_l_u, num_y)
    return (num_x, num_y, chunk_widths, chunk_lengths)
