import { useState, useEffect, useCallback, useRef } from 'react';
import { useSystemState } from './useSystemState';
import { useSelection } from '../components/SelectionContext';
import { getTacticalCover } from '../services/api';
import type { CoverResult } from '../types/schema.generated';
import { SelectionType } from '../types/system';

/**
 * Hook to manage pulling tactical cover data from the backend.
 * Only fetches when the selected token changes or the backend state updates.
 */
export function useTacticalCover() {
  const { tactical_timestamp } = useSystemState();
  const { selection } = useSelection();
  const [bonuses, setBonuses] = useState<Record<number, CoverResult>>({});
  const [isLoading, setIsLoading] = useState(false);
  const lastFetchedVersion = useRef(-1);
  const lastFetchedAttackerId = useRef<number | null>(null);

  const attackerId = selection?.type === SelectionType.TOKEN && selection.id
    ? (typeof selection.id === 'string' ? parseInt(selection.id) : selection.id)
    : null;

  const fetchCover = useCallback(async (id: number, version: number) => {
    setIsLoading(true);
    try {
      const data = await getTacticalCover(id);
      setBonuses(data);
      lastFetchedVersion.current = version;
      lastFetchedAttackerId.current = id;
    } catch (err) {
      console.error('Failed to fetch tactical cover:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (attackerId === null) {
      if (Object.keys(bonuses).length > 0) {
        setBonuses({});
      }
      lastFetchedAttackerId.current = null;
      lastFetchedVersion.current = -1;
      return;
    }

    // Only fetch if selection changed OR backend tactical state changed
    if (attackerId !== lastFetchedAttackerId.current || tactical_timestamp !== lastFetchedVersion.current) {
        fetchCover(attackerId, tactical_timestamp);
    }
    // We omit 'bonuses' from deps to avoid re-triggering when we update results
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attackerId, tactical_timestamp, fetchCover]);

  return { bonuses, isLoading, attackerId };
}
