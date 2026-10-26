import { Navigate, Route, Routes } from 'react-router-dom'

import { AuthGate } from '@/components/auth/AuthGate'
import { AppShell } from '@/components/layout/AppShell'
import { ConsultationPage } from '@/pages/Consultation'
import { Dashboard } from '@/pages/Dashboard'
import { MyBoard } from '@/pages/MyBoard'
import {
  Boardroom,
  CompanyIntelligence,
  DecisionCenter,
  DecisionHistory,
} from '@/pages/Placeholder'

export function App() {
  return (
    <AuthGate>
      <Routes>
        {/* The consultation thread owns the full viewport, so it sits outside
            the shell rather than scrolling inside it. */}
        <Route path="consult/:consultationId" element={<ConsultationPage />} />

        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="board" element={<MyBoard />} />
          <Route path="boardroom/:meetingId?" element={<Boardroom />} />
          <Route path="decisions" element={<DecisionHistory />} />
          <Route path="decisions/:decisionId" element={<DecisionCenter />} />
          <Route path="company" element={<CompanyIntelligence />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthGate>
  )
}
