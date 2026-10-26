import type { ComponentType } from 'react'

import { CeoPortrait } from './ceo'
import { CfoPortrait } from './cfo'
import { CgoPortrait } from './cgo'
import { ChairpersonPortrait } from './chairperson'
import { CompetitiveIntelPortrait } from './competitive-intel'
import { CooPortrait } from './coo'
import { CustomerAdvocatePortrait } from './customer-advocate'
import { GeneralCounselPortrait } from './general-counsel'
import { StrategyConsultantPortrait } from './strategy-consultant'

export interface PortraitProps {
  accent?: string
  accentSoft?: string
  className?: string
}

/**
 * Keyed by the backend `avatar_ref` on each roster entry, so adding or renaming
 * an executive is a one-line change on both sides.
 */
export const EXECUTIVE_PORTRAITS: Record<string, ComponentType<PortraitProps>> = {
  chairperson: ChairpersonPortrait,
  ceo: CeoPortrait,
  coo: CooPortrait,
  cfo: CfoPortrait,
  cgo: CgoPortrait,
  customer_advocate: CustomerAdvocatePortrait,
  competitive_intel: CompetitiveIntelPortrait,
  general_counsel: GeneralCounselPortrait,
  strategy_consultant: StrategyConsultantPortrait,
}

export {
  CeoPortrait,
  CfoPortrait,
  CgoPortrait,
  ChairpersonPortrait,
  CompetitiveIntelPortrait,
  CooPortrait,
  CustomerAdvocatePortrait,
  GeneralCounselPortrait,
  StrategyConsultantPortrait,
}
