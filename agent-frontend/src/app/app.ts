import { Component, DestroyRef, ElementRef, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { interval } from 'rxjs';
import { AlertReport, DeskApi, ToolTrace } from './desk-api';

interface Turn {
  id: number;
  role: 'you' | 'agent';
  text: string;
  tools: ToolTrace[];
  failed: boolean;
}

interface Instrument {
  name: string;
  url: string;
  blurb: string;
}

const BLURBS: Record<string, string> = {
  'k8s-container-metrics': 'Prometheus only. Working set, predict_linear, and a z-score check.',
  'k8s-cluster-openstack': 'Cluster, pod logs, and Nova. The only write is restart_pod.',
};

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private readonly api = inject(DeskApi);
  private readonly destroyRef = inject(DestroyRef);
  private readonly tape = viewChild<ElementRef<HTMLElement>>('tape');
  private seq = 0;

  readonly conversationId = 'desk';
  readonly clock = signal(this.stamp(new Date()));
  readonly online = signal(false);
  readonly busy = signal(false);
  readonly loadError = signal('');
  readonly model = signal('waiting');
  readonly baseUrl = signal('');
  readonly servers = signal<Instrument[]>([]);
  readonly alert = signal<AlertReport | null>(null);
  readonly turns = signal<Turn[]>([]);
  readonly draft = signal('');

  readonly prompts = [
    {
      kicker: '01',
      label: 'Closest to the limit',
      text: 'Which pods are closest to their memory limit right now?',
    },
    {
      kicker: '02',
      label: 'Judge the last alert',
      text: 'Look at the latest memory alert and decide whether deleting that pod is safe.',
    },
    {
      kicker: '03',
      label: 'Pod or hypervisor',
      text: 'Is the pressure coming from the pod, or from the OpenStack compute host?',
    },
  ];

  constructor() {
    interval(1000)
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.clock.set(this.stamp(new Date())));

    interval(15000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.refresh());

    this.refresh();
  }

  refresh(): void {
    this.api.health().subscribe({
      next: () => this.online.set(true),
      error: () => this.markDown(),
    });
    this.api.info().subscribe({
      next: (info) => {
        this.online.set(true);
        this.loadError.set('');
        this.model.set(info.model || 'unknown model');
        this.baseUrl.set(info.baseUrl || '');
        this.servers.set(
          (info.mcp ?? []).map((server) => ({
            name: server.name,
            url: server.url,
            blurb: BLURBS[server.name] ?? 'Connected MCP server.',
          })),
        );
      },
      error: () => this.markDown(),
    });
    this.api.alerts().subscribe({
      next: (report) => this.alert.set(report),
      error: () => undefined,
    });
  }

  send(preset?: string): void {
    const message = (preset ?? this.draft()).trim();
    if (!message || this.busy()) {
      return;
    }
    this.draft.set('');
    this.push({ role: 'you', text: message, tools: [], failed: false });
    this.busy.set(true);
    this.api.chat(this.conversationId, message).subscribe({
      next: (response) => {
        this.busy.set(false);
        if (response.model) {
          this.model.set(response.model);
        }
        const reply = response.reply ?? '';
        this.push({
          role: 'agent',
          text: reply || 'The model returned an empty reply.',
          tools: response.tools ?? [],
          failed: reply.startsWith('The model call failed'),
        });
      },
      error: () => {
        this.busy.set(false);
        this.markDown();
        this.push({
          role: 'agent',
          text: 'The desk could not reach the agent.',
          tools: [],
          failed: true,
        });
      },
    });
  }

  clear(): void {
    this.api.clear(this.conversationId).subscribe({
      next: () => this.turns.set([]),
      error: () => this.loadError.set('The tape stayed. The agent did not accept the clear.'),
    });
  }

  onDraft(event: Event): void {
    const target = event.target as HTMLTextAreaElement;
    this.draft.set(target.value);
  }

  onKey(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  onSubmit(event: Event): void {
    event.preventDefault();
    this.send();
  }

  when(iso: string | null): string {
    if (!iso) {
      return '';
    }
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) {
      return iso;
    }
    return new Intl.DateTimeFormat('en-GB', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    }).format(date);
  }

  pretty(raw: string): string {
    try {
      return JSON.stringify(JSON.parse(raw), null, 2);
    } catch {
      return raw;
    }
  }

  status(): string {
    if (this.busy()) {
      return 'Reading the instruments';
    }
    if (!this.online()) {
      return 'Agent unreachable';
    }
    return 'Listening';
  }

  private markDown(): void {
    this.online.set(false);
    this.loadError.set('The agent on port 8080 is not answering.');
  }

  private push(turn: Omit<Turn, 'id'>): void {
    this.seq += 1;
    this.turns.update((turns) => [...turns, { ...turn, id: this.seq }]);
    this.stick();
  }

  private stick(): void {
    queueMicrotask(() => {
      const el = this.tape()?.nativeElement;
      if (el) {
        el.scrollTop = el.scrollHeight;
      }
    });
  }

  private stamp(date: Date): string {
    return new Intl.DateTimeFormat('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    }).format(date);
  }
}
