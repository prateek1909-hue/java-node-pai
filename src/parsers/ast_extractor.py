"""
AST extraction utilities for tree-sitter Java parsing.
Helper functions for traversing and extracting information from syntax trees.
"""

from typing import Optional, List, Union
from tree_sitter import Node


class ASTExtractor:
    """Utility class for extracting information from tree-sitter AST nodes."""

    @staticmethod
    def get_node_text(node: Optional[Node], source: str) -> str:
        """
        Extract text from a tree-sitter node.

        Args:
            node: The tree-sitter node
            source: The source code string

        Returns:
            The text content of the node, or empty string if node is None
        """
        if not node:
            return ""
        return source[node.start_byte : node.end_byte]

    @staticmethod
    def find_parent_by_type(
        node: Node, types: Union[str, List[str]]
    ) -> Optional[Node]:
        """
        Find the first parent node of specific type(s).

        Args:
            node: The starting node
            types: Single type string or list of type strings to search for

        Returns:
            The parent node of matching type, or None if not found
        """
        if isinstance(types, str):
            types = [types]

        current = node.parent
        while current:
            if current.type in types:
                return current
            current = current.parent
        return None

    @staticmethod
    def get_children_by_type(node: Node, node_type: str) -> List[Node]:
        """
        Get all direct children of a specific type.

        Args:
            node: The parent node
            node_type: The type of children to find

        Returns:
            List of child nodes matching the type
        """
        return [child for child in node.children if child.type == node_type]

    @staticmethod
    def find_child_by_type(node: Node, node_type: str) -> Optional[Node]:
        """
        Find the first direct child of a specific type.

        Args:
            node: The parent node
            node_type: The type of child to find

        Returns:
            The first child node matching the type, or None
        """
        for child in node.children:
            if child.type == node_type:
                return child
        return None

    @staticmethod
    def find_child_by_field(node: Node, field_name: str) -> Optional[Node]:
        """
        Find a child node by field name.

        Args:
            node: The parent node
            field_name: The field name to search for

        Returns:
            The child node with matching field, or None
        """
        return node.child_by_field_name(field_name)

    @staticmethod
    def get_all_descendants_by_type(node: Node, node_type: str) -> List[Node]:
        """
        Get all descendant nodes of a specific type (recursive).

        Args:
            node: The root node
            node_type: The type to search for

        Returns:
            List of all descendant nodes matching the type
        """
        matches: List[Node] = []

        def traverse(n: Node) -> None:
            if n.type == node_type:
                matches.append(n)
            for child in n.children:
                traverse(child)

        traverse(node)
        return matches

    @staticmethod
    def has_child_of_type(node: Node, node_type: str) -> bool:
        """
        Check if node has any direct child of specific type.

        Args:
            node: The parent node
            node_type: The type to check for

        Returns:
            True if child of type exists, False otherwise
        """
        return any(child.type == node_type for child in node.children)

    @staticmethod
    def get_node_range(node: Node) -> tuple[int, int, int, int]:
        """
        Get the line and column range of a node.

        Args:
            node: The tree-sitter node

        Returns:
            Tuple of (start_line, start_col, end_line, end_col)
        """
        return (
            node.start_point[0],
            node.start_point[1],
            node.end_point[0],
            node.end_point[1],
        )

    @staticmethod
    def get_line_range(node: Node) -> tuple[int, int]:
        """
        Get the line range of a node (1-indexed for display).

        Args:
            node: The tree-sitter node

        Returns:
            Tuple of (start_line, end_line) 1-indexed
        """
        return (node.start_point[0] + 1, node.end_point[0] + 1)

    @staticmethod
    def is_error_node(node: Node) -> bool:
        """
        Check if node is an error node.

        Args:
            node: The tree-sitter node

        Returns:
            True if node is an error, False otherwise
        """
        return node.type == "ERROR" or node.is_missing

    @staticmethod
    def traverse_tree(node: Node, callback) -> None:  # type: ignore
        """
        Traverse the entire syntax tree depth-first.

        Args:
            node: The root node
            callback: Function to call for each node (receives node as argument)
        """

        def traverse(n: Node) -> None:
            callback(n)
            for child in n.children:
                traverse(child)

        traverse(node)

    @staticmethod
    def find_nodes_between_lines(
        root: Node, start_line: int, end_line: int
    ) -> List[Node]:
        """
        Find all nodes that fall within a line range.

        Args:
            root: The root node to search from
            start_line: Starting line (0-indexed)
            end_line: Ending line (0-indexed)

        Returns:
            List of nodes within the line range
        """
        matches: List[Node] = []

        def traverse(n: Node) -> None:
            node_start = n.start_point[0]
            node_end = n.end_point[0]

            # Check if node overlaps with range
            if node_start <= end_line and node_end >= start_line:
                matches.append(n)
                for child in n.children:
                    traverse(child)

        traverse(root)
        return matches

    @staticmethod
    def get_siblings(node: Node) -> List[Node]:
        """
        Get all sibling nodes.

        Args:
            node: The node to get siblings for

        Returns:
            List of sibling nodes (excluding the node itself)
        """
        if not node.parent:
            return []
        return [child for child in node.parent.children if child != node]

    @staticmethod
    def get_next_sibling(node: Node) -> Optional[Node]:
        """
        Get the next sibling node.

        Args:
            node: The current node

        Returns:
            The next sibling, or None if this is the last child
        """
        return node.next_sibling

    @staticmethod
    def get_previous_sibling(node: Node) -> Optional[Node]:
        """
        Get the previous sibling node.

        Args:
            node: The current node

        Returns:
            The previous sibling, or None if this is the first child
        """
        return node.prev_sibling

    @staticmethod
    def count_children(node: Node) -> int:
        """
        Count the number of children.

        Args:
            node: The parent node

        Returns:
            Number of children
        """
        return node.child_count

    @staticmethod
    def is_named_node(node: Node) -> bool:
        """
        Check if this is a named node (vs. anonymous like punctuation).

        Args:
            node: The tree-sitter node

        Returns:
            True if named node, False otherwise
        """
        return node.is_named
