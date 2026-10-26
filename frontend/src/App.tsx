import { Navigate, Route, Routes } from 'react-router-dom'

import { AuthGate } from '@/components/auth/AuthGate'
import { AppShell } from '@/components/layout/AppShell'
import { BoardroomPage } from '@/pages/Boardroom'
import { ConsultationPage } from '@/pages/Consultation'
import { Dashboard } from '@/pages/Dashboard'
import { DecisionCenterPage } from '@/pages/DecisionCenter'
import { MeetingsPage } from '@/pages/Meetings'
import { MyBoard } from '@/pages/MyBoard'
import { NewMeetingPage } from '@/pages/NewMeeting'
import { CompanyIntelligencePage } from '@/pages/CompanyIntelligence'

export function App() {
  return (
    <AuthGate>
      <Routes>
        {/* Full-viewport surfaces: these own their own scrolling and chrome. */}
        <Route path="consult/:consultationId" element={<ConsultationPage />} />
        <Route path="boardroom/:meetingId" element={<BoardroomPage />} />

        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="board" element={<MyBoard />} />
          <Route path="meetings" element={<MeetingsPage />} />
          <Route path="meetings/new" element={<NewMeetingPage />} />
          <Route path="decisions/:decisionId" element={<DecisionCenterPage />} />
          <Route path="company" element={<CompanyIntelligencePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthGate>
  )
}
