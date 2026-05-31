import { Suspense } from 'react'
import ChatInterface from '@/components/chat/ChatInterface'

export default function Home() {
  return (
    <Suspense>
      <ChatInterface />
    </Suspense>
  )
}
