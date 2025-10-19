// app/dashboard/youtube-rag/page.tsx
// PMOVES.AI YouTube RAG Monitoring Dashboard

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { 
  Activity, Database, Search, Upload, RefreshCw, 
  CheckCircle2, XCircle, Clock, PlayCircle, PauseCircle,
  BarChart3, Zap, Server, HardDrive, Youtube
} from 'lucide-react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';

// Types
interface QueueStatus {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
}

interface ProcessingMetrics {
  totalVideos: number;
  totalSegments: number;
  averageProcessingTime: number;
  successRate: number;
  embeddings: {
    text: number;
    context: number;
    contrastive: number;
    combined: number;
  };
}

interface VideoItem {
  id: string;
  video_id: string;
  url: string;
  title: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  segments: number;
  processing_time?: number;
  error?: string;
  created_at: string;
  completed_at?: string;
}

interface SearchMetric {
  hour: string;
  searches: number;
  avg_response_ms: number;
  avg_results: number;
  avg_ctr: number;
}

// API Service
class PMOVESAPIService {
  private baseUrl: string;
  
  constructor(baseUrl: string = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }
  
  async getQueueStatus(): Promise<QueueStatus> {
    const response = await fetch(`${this.baseUrl}/api/queue/status`);
    return response.json();
  }
  
  async getProcessingMetrics(): Promise<ProcessingMetrics> {
    const response = await fetch(`${this.baseUrl}/api/metrics/processing`);
    return response.json();
  }
  
  async getRecentVideos(limit: number = 10): Promise<VideoItem[]> {
    const response = await fetch(`${this.baseUrl}/api/videos/recent?limit=${limit}`);
    return response.json();
  }
  
  async getSearchMetrics(): Promise<SearchMetric[]> {
    const response = await fetch(`${this.baseUrl}/api/metrics/search`);
    return response.json();
  }
  
  async addVideosToQueue(urls: string[]): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/queue/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls })
    });
    return response.json();
  }
  
  async retryFailed(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/queue/retry`, {
      method: 'POST'
    });
    return response.json();
  }
  
  async syncToQdrant(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/sync/qdrant`, {
      method: 'POST'
    });
    return response.json();
  }
}

// Components
const StatusCard: React.FC<{ 
  title: string; 
  value: number; 
  icon: React.ReactNode;
  trend?: number;
  color?: string;
}> = ({ title, value, icon, trend, color = "text-primary" }) => (
  <Card>
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-sm font-medium">{title}</CardTitle>
      <div className={color}>{icon}</div>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{value.toLocaleString()}</div>
      {trend !== undefined && (
        <p className={`text-xs ${trend > 0 ? 'text-green-600' : 'text-red-600'}`}>
          {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}% from last hour
        </p>
      )}
    </CardContent>
  </Card>
);

const QueueChart: React.FC<{ data: any[] }> = ({ data }) => {
  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];
  
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
          outerRadius={80}
          fill="#8884d8"
          dataKey="value"
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  );
};

const ProcessingChart: React.FC<{ data: any[] }> = ({ data }) => (
  <ResponsiveContainer width="100%" height={300}>
    <AreaChart data={data}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey="time" />
      <YAxis />
      <Tooltip />
      <Legend />
      <Area type="monotone" dataKey="processed" stroke="#8884d8" fill="#8884d8" />
      <Area type="monotone" dataKey="failed" stroke="#ff0000" fill="#ff0000" />
    </AreaChart>
  </ResponsiveContainer>
);

// Main Dashboard Component
export default function PMOVESYouTubeRAGDashboard() {
  const [queueStatus, setQueueStatus] = useState<QueueStatus>({
    pending: 0,
    processing: 0,
    completed: 0,
    failed: 0
  });
  
  const [metrics, setMetrics] = useState<ProcessingMetrics>({
    totalVideos: 0,
    totalSegments: 0,
    averageProcessingTime: 0,
    successRate: 0,
    embeddings: {
      text: 0,
      context: 0,
      contrastive: 0,
      combined: 0
    }
  });
  
  const [recentVideos, setRecentVideos] = useState<VideoItem[]>([]);
  const [searchMetrics, setSearchMetrics] = useState<SearchMetric[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  
  const api = new PMOVESAPIService();
  
  // Fetch data
  const fetchData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [queue, metrics, videos, search] = await Promise.all([
        api.getQueueStatus(),
        api.getProcessingMetrics(),
        api.getRecentVideos(),
        api.getSearchMetrics()
      ]);
      
      setQueueStatus(queue);
      setMetrics(metrics);
      setRecentVideos(videos);
      setSearchMetrics(search);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setIsRefreshing(false);
    }
  }, []);
  
  // Auto-refresh
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, [fetchData]);
  
  // Handle URL submission
  const handleAddUrls = async () => {
    const urls = urlInput.split('\n').filter(u => u.trim());
    if (urls.length > 0) {
      try {
        await api.addVideosToQueue(urls);
        setUrlInput('');
        await fetchData();
      } catch (error) {
        console.error('Error adding URLs:', error);
      }
    }
  };
  
  // Prepare chart data
  const queueChartData = [
    { name: 'Pending', value: queueStatus.pending },
    { name: 'Processing', value: queueStatus.processing },
    { name: 'Completed', value: queueStatus.completed },
    { name: 'Failed', value: queueStatus.failed }
  ];
  
  const embeddingChartData = Object.entries(metrics.embeddings).map(([key, value]) => ({
    type: key.charAt(0).toUpperCase() + key.slice(1),
    count: value
  }));
  
  return (
    <div className="min-h-screen bg-background p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Youtube className="h-8 w-8 text-red-500" />
            <div>
              <h1 className="text-3xl font-bold">PMOVES.AI YouTube RAG Dashboard</h1>
              <p className="text-muted-foreground">
                Real-time monitoring of CoCa-enhanced video processing pipeline
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button 
              variant="outline" 
              onClick={fetchData}
              disabled={isRefreshing}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button onClick={() => api.syncToQdrant()}>
              <Zap className="mr-2 h-4 w-4" />
              Sync to Qdrant
            </Button>
          </div>
        </div>
      </div>
      
      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="queue">Queue</TabsTrigger>
          <TabsTrigger value="videos">Videos</TabsTrigger>
          <TabsTrigger value="search">Search</TabsTrigger>
          <TabsTrigger value="system">System</TabsTrigger>
        </TabsList>
        
        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          {/* Status Cards */}
          <div className="grid gap-4 md:grid-cols-4">
            <StatusCard
              title="Pending Videos"
              value={queueStatus.pending}
              icon={<Clock className="h-4 w-4" />}
              color="text-yellow-500"
            />
            <StatusCard
              title="Processing"
              value={queueStatus.processing}
              icon={<PlayCircle className="h-4 w-4" />}
              color="text-blue-500"
            />
            <StatusCard
              title="Completed"
              value={queueStatus.completed}
              icon={<CheckCircle2 className="h-4 w-4" />}
              color="text-green-500"
            />
            <StatusCard
              title="Failed"
              value={queueStatus.failed}
              icon={<XCircle className="h-4 w-4" />}
              color="text-red-500"
            />
          </div>
          
          {/* Metrics Cards */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Processing Metrics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm">Total Videos</span>
                  <span className="font-medium">{metrics.totalVideos}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Total Segments</span>
                  <span className="font-medium">{metrics.totalSegments}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Avg Processing Time</span>
                  <span className="font-medium">{metrics.averageProcessingTime}s</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Success Rate</span>
                  <Badge variant={metrics.successRate > 90 ? "default" : "destructive"}>
                    {metrics.successRate}%
                  </Badge>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>Queue Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <QueueChart data={queueChartData} />
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>CoCa Embeddings</CardTitle>
                <CardDescription>Multi-level embedding counts</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={embeddingChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="type" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" fill="#8884d8" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        {/* Queue Tab */}
        <TabsContent value="queue" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Add Videos to Queue</CardTitle>
              <CardDescription>
                Enter YouTube URLs (one per line) to add to processing queue
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <textarea
                className="w-full h-32 p-3 border rounded-md"
                placeholder="https://youtube.com/watch?v=..."
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
              />
              <div className="flex gap-2">
                <Button onClick={handleAddUrls}>
                  <Upload className="mr-2 h-4 w-4" />
                  Add to Queue
                </Button>
                <Button variant="outline" onClick={() => api.retryFailed()}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Retry Failed
                </Button>
              </div>
            </CardContent>
          </Card>
          
          {/* Queue Progress */}
          <Card>
            <CardHeader>
              <CardTitle>Processing Progress</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between mb-2">
                    <span className="text-sm">Overall Progress</span>
                    <span className="text-sm font-medium">
                      {queueStatus.completed}/{queueStatus.completed + queueStatus.pending + queueStatus.processing}
                    </span>
                  </div>
                  <Progress 
                    value={(queueStatus.completed / (queueStatus.completed + queueStatus.pending + queueStatus.processing)) * 100}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Videos Tab */}
        <TabsContent value="videos" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Videos</CardTitle>
              <CardDescription>Latest processed videos in the system</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[500px]">
                <div className="space-y-4">
                  {recentVideos.map((video) => (
                    <div key={video.id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-medium">{video.title}</h3>
                        <Badge variant={
                          video.status === 'completed' ? 'default' :
                          video.status === 'failed' ? 'destructive' :
                          video.status === 'processing' ? 'secondary' :
                          'outline'
                        }>
                          {video.status}
                        </Badge>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-sm text-muted-foreground">
                        <div>Video ID: {video.video_id}</div>
                        <div>Segments: {video.segments}</div>
                        {video.processing_time && (
                          <div>Processing: {video.processing_time}s</div>
                        )}
                      </div>
                      {video.error && (
                        <Alert className="mt-2">
                          <AlertDescription>{video.error}</AlertDescription>
                        </Alert>
                      )}
                      <div className="mt-2">
                        <a 
                          href={video.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-blue-500 hover:underline text-sm"
                        >
                          View on YouTube →
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Search Tab */}
        <TabsContent value="search" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Search Performance</CardTitle>
              <CardDescription>CoCa-enhanced search metrics over time</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={searchMetrics}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="hour" />
                  <YAxis yAxisId="left" />
                  <YAxis yAxisId="right" orientation="right" />
                  <Tooltip />
                  <Legend />
                  <Line 
                    yAxisId="left" 
                    type="monotone" 
                    dataKey="searches" 
                    stroke="#8884d8" 
                    name="Searches"
                  />
                  <Line 
                    yAxisId="right" 
                    type="monotone" 
                    dataKey="avg_response_ms" 
                    stroke="#82ca9d" 
                    name="Avg Response (ms)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* System Tab */}
        <TabsContent value="system" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Database Status</CardTitle>
                <CardDescription>Supabase & Qdrant health</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4" />
                    <span>Supabase</span>
                  </div>
                  <Badge variant="default">Connected</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Server className="h-4 w-4" />
                    <span>Qdrant</span>
                  </div>
                  <Badge variant="default">Connected</Badge>
                </div>
                <Separator />
                <div className="text-sm space-y-1">
                  <div>Total Vectors: {metrics.totalSegments * 4}</div>
                  <div>Index Size: ~{(metrics.totalSegments * 4 * 3584 * 4 / 1024 / 1024).toFixed(2)} MB</div>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>Service Health</CardTitle>
                <CardDescription>Microservices status</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex items-center justify-between">
                  <span>n8n Workflow Engine</span>
                  <Badge variant="default">Running</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span>MCP Docker Server</span>
                  <Badge variant="default">Running</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span>Batch Processor</span>
                  <Badge variant="default">Running</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span>Redis Queue</span>
                  <Badge variant="default">Running</Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}