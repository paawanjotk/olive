import type { Edge, Node } from '@xyflow/react'
import type { GraphJson, WorkflowNodeType } from './types'

// Edges leaving a supervisor are "delegated" (LLM decides) → dotted + animated.
// All other edges are "deterministic" → solid. This is the visual language that
// makes the canvas a possibility space rather than a fixed script.
export function styleEdges(nodes: Node[], edges: Edge[]): Edge[] {
  const typeById = new Map(nodes.map((n) => [n.id, n.type]))
  return edges.map((e) => {
    const delegated = typeById.get(e.source) === 'supervisor'
    return {
      ...e,
      animated: delegated,
      style: delegated
        ? { stroke: '#fbbf24', strokeWidth: 1.5, strokeDasharray: '6 5' }
        : { stroke: 'rgba(255,255,255,0.25)', strokeWidth: 1.5 },
    }
  })
}

export function graphToFlow(graph: GraphJson): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = (graph.nodes ?? []).map((n) => ({
    id: n.id,
    type: n.type,
    position: n.position ?? { x: 0, y: 0 },
    data: { ...n.data },
  }))
  const edges: Edge[] = (graph.edges ?? []).map((e) => ({
    id: e.id ?? `${e.source}->${e.target}`,
    source: e.source,
    target: e.target,
  }))
  return { nodes, edges: styleEdges(nodes, edges) }
}

// Serialize React Flow state back to graph_json, stripping runtime-only fields.
export function flowToGraph(nodes: Node[], edges: Edge[]): GraphJson {
  return {
    nodes: nodes.map((n) => {
      const { status, ...data } = (n.data ?? {}) as Record<string, unknown>
      return {
        id: n.id,
        type: (n.type ?? 'agent') as WorkflowNodeType,
        position: n.position,
        data: data as { label: string; description?: string; agentId?: string },
      }
    }),
    edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
  }
}
