import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ErrorCode, ListToolsRequestSchema, McpError, } from '@modelcontextprotocol/sdk/types.js';
import { OAuth2Client } from 'google-auth-library';
import * as dotenv from 'dotenv';
dotenv.config();
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID;
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET;
const GOOGLE_REFRESH_TOKEN = process.env.GOOGLE_REFRESH_TOKEN;
class NotebookLmAgent {
    server;
    oauth2Client;
    constructor() {
        this.server = new Server({
            name: 'notebooklm-mcp-agent',
            version: '1.0.0',
        }, {
            capabilities: {
                tools: {},
            },
        });
        this.oauth2Client = new OAuth2Client(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET);
        if (GOOGLE_REFRESH_TOKEN) {
            this.oauth2Client.setCredentials({
                refresh_token: GOOGLE_REFRESH_TOKEN
            });
        }
        this.setupToolHandlers();
        // Error handling
        this.server.onerror = (error) => console.error('[MCP Error]', error);
        process.on('SIGINT', async () => {
            await this.server.close();
            process.exit(0);
        });
    }
    setupToolHandlers() {
        this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
            tools: [
                {
                    name: 'notebooklm_list_notebooks',
                    description: 'Lists all NotebookLM notebooks for the authenticated user.',
                    inputSchema: {
                        type: 'object',
                        properties: {},
                    },
                },
                {
                    name: 'notebooklm_query',
                    description: 'Queries a specific NotebookLM notebook.',
                    inputSchema: {
                        type: 'object',
                        properties: {
                            notebookId: {
                                type: 'string',
                                description: 'The ID of the NotebookLM notebook.',
                            },
                            query: {
                                type: 'string',
                                description: 'The query to ask the notebook.',
                            },
                        },
                        required: ['notebookId', 'query'],
                    },
                },
            ],
        }));
        this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
            if (!GOOGLE_REFRESH_TOKEN) {
                throw new McpError(ErrorCode.InvalidRequest, 'Not authenticated with Google (missing GOOGLE_REFRESH_TOKEN).');
            }
            switch (request.params.name) {
                case 'notebooklm_list_notebooks': {
                    // TODO: Implement actual NotebookLM undocumented API call using this.oauth2Client
                    return {
                        content: [
                            {
                                type: 'text',
                                text: 'NotebookLM API integration placeholder. Scopes applied successfully.',
                            },
                        ],
                    };
                }
                case 'notebooklm_query': {
                    const { notebookId, query } = request.params.arguments;
                    return {
                        content: [
                            {
                                type: 'text',
                                text: `NotebookLM query integration placeholder. Notebook: ${notebookId}, Query: ${query}`,
                            },
                        ],
                    };
                }
                default:
                    throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${request.params.name}`);
            }
        });
    }
    async run() {
        const transport = new StdioServerTransport();
        await this.server.connect(transport);
        console.error('NotebookLM MCP agent running on stdio');
    }
}
const agent = new NotebookLmAgent();
agent.run().catch(console.error);
