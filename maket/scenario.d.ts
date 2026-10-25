export interface Card {
  id: string
  source_type: string
  title: string
  source_name?: string
  published_at?: string
  anchor?: { url?: string; path?: string }
}

export interface Client {
  id: string
  name: string
  sector: string
  region: string
  finance: string
  features: { id: string; text: string }[]
}

export interface Happened {
  kind?: string
  label?: string
  gloss?: string
  source?: string
  title?: string
  href?: string
}

export interface Story {
  id: string
  title: string
  why: string
  factors: { label: string }[]
  happened: Happened[]
  whyCompany: string[]
  risks: string[]
  opportunities: string[]
  action: string
  actionWhy: string
  bank: { role: string; text: string; source: string; href?: string }[]
  conclusion: string
  sources: { kind: string; name: string; title: string; href?: string }[]
  trace: { name: string; text: string }[]
  featuresUsed: string[]
}

export const Scenario: {
  clients: Client[]
  storiesFor: (clientId: string, cards: Card[]) => Story[]
  answerQuestion: (
    clientId: string,
    cards: Card[],
    question: string,
  ) => { error?: string; event?: Story }
}
