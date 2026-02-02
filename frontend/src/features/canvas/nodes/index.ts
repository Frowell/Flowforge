/**
 * Node type registry — maps node type strings to React Flow custom node components.
 */

import type { NodeTypes } from "@xyflow/react";
import DataSourceNode from "./DataSourceNode";
import FilterNode from "./FilterNode";
import SelectNode from "./SelectNode";
import SortNode from "./SortNode";
import JoinNode from "./JoinNode";
import GroupByNode from "./GroupByNode";
import FormulaNode from "./FormulaNode";
import ChartOutputNode from "./ChartOutputNode";
import TableOutputNode from "./TableOutputNode";
import RenameNode from "./RenameNode";
import UniqueNode from "./UniqueNode";
import SampleNode from "./SampleNode";
import UnionNode from "./UnionNode";
import PivotNode from "./PivotNode";

export const nodeTypes: NodeTypes = {
  data_source: DataSourceNode,
  filter: FilterNode,
  select: SelectNode,
  sort: SortNode,
  join: JoinNode,
  union: UnionNode,
  group_by: GroupByNode,
  pivot: PivotNode,
  formula: FormulaNode,
  rename: RenameNode,
  unique: UniqueNode,
  sample: SampleNode,
  chart_output: ChartOutputNode,
  table_output: TableOutputNode,
};
