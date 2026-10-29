/**
 * Tests for the map legend: it lists only the pathway types the map draws,
 * as named by the server's ``drawnTypes`` config (issues #166, #172).
 */

import { describe, it, expect } from 'vitest';
import { renderPathwayLegend } from './map-core';

describe('renderPathwayLegend', () => {
    it('shows exactly the drawn types, in the order given', () => {
        const section = document.createElement('div');

        renderPathwayLegend(section, ['conduit_bank', 'conduit', 'aerial', 'direct_buried', 'submarine']);

        const labels = Array.from(section.querySelectorAll('.pw-legend-label')).map(el => el.textContent);
        expect(labels).toEqual(['Conduit Bank', 'Conduit', 'Aerial', 'Direct Buried', 'Submarine']);
    });

    it('draws each type with its own line style', () => {
        const section = document.createElement('div');

        renderPathwayLegend(section, ['submarine']);

        const line = section.querySelector('line');
        expect(line?.getAttribute('stroke')).toBe('#1a237e');
        expect(line?.getAttribute('stroke-dasharray')).toBe('6,2,2,2');
    });
});
