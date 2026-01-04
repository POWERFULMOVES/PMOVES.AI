export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export interface Database {
  public: {
    Tables: {
      upload_events: {
        Row: {
          id: number;
          upload_id: string;
          filename: string | null;
          bucket: string | null;
          object_key: string | null;
          status: string | null;
          progress: number | null;
          error_message: string | null;
          size_bytes: number | null;
          content_type: string | null;
          meta: Json | null;
          created_at: string;
          updated_at: string;
          owner_id: string | null;
        };
        Insert: {
          id?: number;
          upload_id: string;
          filename?: string | null;
          bucket?: string | null;
          object_key?: string | null;
          status?: string | null;
          progress?: number | null;
          error_message?: string | null;
          size_bytes?: number | null;
          content_type?: string | null;
          meta?: Json | null;
          created_at?: string;
          updated_at?: string;
          owner_id?: string | null;
        };
        Update: {
          id?: number;
          upload_id?: string;
          filename?: string | null;
          bucket?: string | null;
          object_key?: string | null;
          status?: string | null;
          progress?: number | null;
          error_message?: string | null;
          size_bytes?: number | null;
          content_type?: string | null;
          meta?: Json | null;
          created_at?: string;
          updated_at?: string;
          owner_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: 'upload_events_owner_id_fkey';
            columns: ['owner_id'];
            referencedRelation: 'users';
            referencedColumns: ['id'];
          }
        ];
      };
      studio_board: {
        Row: {
          id: number;
          title: string | null;
          namespace: string | null;
          status: string | null;
          content_url: string | null;
          created_at: string;
          meta: Json | null;
        };
        Insert: {
          id?: number;
          title?: string | null;
          namespace?: string | null;
          status?: string | null;
          content_url?: string | null;
          created_at?: string;
          meta?: Json | null;
        };
        Update: {
          id?: number;
          title?: string | null;
          namespace?: string | null;
          status?: string | null;
          content_url?: string | null;
          created_at?: string;
          meta?: Json | null;
        };
        Relationships: [];
      };
      videos: {
        Row: {
          id: number;
          video_id: string;
          namespace: string | null;
          title: string | null;
          source_url: string | null;
          s3_base_prefix: string | null;
          created_at: string;
          meta: Json | null;
        };
        Insert: {
          id?: number;
          video_id: string;
          namespace?: string | null;
          title?: string | null;
          source_url?: string | null;
          s3_base_prefix?: string | null;
          created_at?: string;
          meta?: Json | null;
        };
        Update: {
          id?: number;
          video_id?: string;
          namespace?: string | null;
          title?: string | null;
          source_url?: string | null;
          s3_base_prefix?: string | null;
          created_at?: string;
          meta?: Json | null;
        };
        Relationships: [];
      };
      transcripts: {
        Row: {
          id: number;
          video_id: string;
          language: string;
          text: string | null;
          s3_uri: string | null;
          created_at: string;
          meta: Json | null;
        };
        Insert: {
          id?: number;
          video_id: string;
          language: string;
          text?: string | null;
          s3_uri?: string | null;
          created_at?: string;
          meta?: Json | null;
        };
        Update: {
          id?: number;
          video_id?: string;
          language?: string;
          text?: string | null;
          s3_uri?: string | null;
          created_at?: string;
          meta?: Json | null;
        };
        Relationships: [];
      };
      snapshots: {
        Row: {
          id: string;
          thread_id: string;
          name: string;
          at: string;
          tags: string[] | null;
          position: number | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          thread_id: string;
          name: string;
          at: string;
          tags?: string[] | null;
          position?: number | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          thread_id?: string;
          name?: string;
          at?: string;
          tags?: string[] | null;
          position?: number | null;
          created_at?: string;
        };
        Relationships: [];
      };
      view_groups: {
        Row: {
          id: string;
          thread_id: string;
          name: string;
          constraints: Json | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          thread_id: string;
          name: string;
          constraints?: Json | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          thread_id?: string;
          name?: string;
          constraints?: Json | null;
          created_at?: string;
        };
        Relationships: [];
      };
      view_group_members: {
        Row: {
          id: string;
          group_id: string;
          message_id: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          group_id: string;
          message_id: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          group_id?: string;
          message_id?: string;
          created_at?: string;
        };
        Relationships: [];
      };
      view_group_actions: {
        Row: {
          id: string;
          group_id: string;
          action: string;
          params: Json | null;
          applied_to_message_ids: string[];
          created_at: string;
        };
        Insert: {
          id?: string;
          group_id: string;
          action: string;
          params?: Json | null;
          applied_to_message_ids?: string[];
          created_at?: string;
        };
        Update: {
          id?: string;
          group_id?: string;
          action?: string;
          params?: Json | null;
          applied_to_message_ids?: string[];
          created_at?: string;
        };
        Relationships: [];
      };
      chat_messages: {
        Row: {
          id: string;
          thread_id: string | null;
          owner_id: string | null;
          content: string | null;
          role: string | null;
          agent: string | null;
          avatar_url: string | null;
          text: string | null;
          cgp: Json | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          thread_id?: string | null;
          owner_id?: string | null;
          content?: string | null;
          role?: string | null;
          agent?: string | null;
          avatar_url?: string | null;
          text?: string | null;
          cgp?: Json | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          thread_id?: string | null;
          owner_id?: string | null;
          content?: string | null;
          role?: string | null;
          agent?: string | null;
          avatar_url?: string | null;
          text?: string | null;
          cgp?: Json | null;
          created_at?: string;
        };
        Relationships: [];
      };
      content_blocks: {
        Row: {
          id: string;
          message_id: string;
          kind: string;
          uri: string | null;
          meta: Json | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          message_id: string;
          kind: string;
          uri?: string | null;
          meta?: Json | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          message_id?: string;
          kind?: string;
          uri?: string | null;
          meta?: Json | null;
          created_at?: string;
        };
        Relationships: [];
      };
      message_views: {
        Row: {
          id: string;
          message_id: string;
          block_id: string;
          archetype: string;
          variant: string | null;
          seed: number | null;
          layout: Json | null;
          style: Json | null;
          locked: boolean | null;
          visible: boolean | null;
          z: number | null;
          created_by: string | null;
          created_at: string | null;
        };
        Insert: {
          id?: string;
          message_id: string;
          block_id: string;
          archetype: string;
          variant?: string | null;
          seed?: number | null;
          layout?: Json | null;
          style?: Json | null;
          locked?: boolean | null;
          visible?: boolean | null;
          z?: number | null;
          created_by?: string | null;
          created_at?: string | null;
        };
        Update: {
          id?: string;
          message_id?: string;
          block_id?: string;
          archetype?: string;
          variant?: string | null;
          seed?: number | null;
          layout?: Json | null;
          style?: Json | null;
          locked?: boolean | null;
          visible?: boolean | null;
          z?: number | null;
          created_by?: string | null;
          created_at?: string | null;
        };
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: {
      rpc_snapshot_ticks: {
        Args: {
          p_thread_id: string;
          p_limit?: number | null;
        };
        Returns: {
          tick: string;
          source: string | null;
          id: string;
        }[];
      };
      rpc_snapshot_views: {
        Args: {
          p_thread_id: string;
          p_at: string;
        };
        Returns: {
          message_id: string;
          view_id: string | null;
          block_id: string | null;
          archetype: string | null;
          variant: string | null;
          seed: number | null;
          layout: Json | null;
          style: Json | null;
          locked: boolean | null;
          visible: boolean | null;
          z: number | null;
          created_at: string | null;
        }[];
      };
    };
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
  pmoves_core: {
    Tables: {
      personas: {
        Row: {
          name: string;
          version: number | null;
          description: string | null;
          runtime: Json | null;
        };
        Insert: {
          name: string;
          version?: number | null;
          description?: string | null;
          runtime?: Json | null;
        };
        Update: {
          name?: string;
          version?: number | null;
          description?: string | null;
          runtime?: Json | null;
        };
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
}
