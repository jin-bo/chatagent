#!/usr/bin/env python3
"""Test skill resource loading."""

from pathlib import Path
from chatagent.skills import SkillManager


def test_skill_resources():
    """Test that skill resources are properly listed."""
    # Initialize skill manager
    skill_manager = SkillManager()

    # Test with standard-review skill
    print("Testing standard-review skill:")
    print("-" * 60)

    # Check if skill exists
    available_skills = skill_manager.list_available_skills()
    print(f"Available skills: {', '.join(available_skills)}")

    if "standard-review" not in available_skills:
        print("\nError: standard-review skill not found!")
        return

    # Activate the skill
    result = skill_manager.activate_skill(
        "standard-review",
        "Review a standard document"
    )

    print("\n" + result)

    # Also test the internal method directly
    print("\n" + "=" * 60)
    print("Direct resource listing:")
    print("=" * 60)
    resources = skill_manager._list_skill_resources("standard-review")

    print(f"\nReferences found: {len(resources['references'])}")
    for ref in resources["references"]:
        print(f"  - {ref}")
        # Verify file exists
        if Path(ref).exists():
            print(f"    ✓ File exists")
        else:
            print(f"    ✗ File not found!")

    print(f"\nAssets found: {len(resources['assets'])}")
    for asset in resources["assets"]:
        print(f"  - {asset}")
        # Verify file exists
        if Path(asset).exists():
            print(f"    ✓ File exists")
        else:
            print(f"    ✗ File not found!")


if __name__ == "__main__":
    test_skill_resources()
