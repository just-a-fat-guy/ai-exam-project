export const dynamic = 'force-dynamic';
export const maxDuration = 600;

import { NextResponse } from 'next/server';

export async function GET(request: Request, { params }: { params: { slug: string[] } }) {
  const backendUrl = process.env.NEXT_PUBLIC_GPTR_API_URL || 'http://localhost:8000';
  
  try {
    const { searchParams } = new URL(request.url);
    
    // Build the endpoint path
    const slugPath = params.slug.join('/');
    let endpoint = '/api/exam-papers';
    if (slugPath) {
      endpoint += `/${slugPath}`;
    }
    
    // Add query params
    const paramsStr = new URLSearchParams();
    Array.from(searchParams.entries()).forEach(([key, value]) => {
      paramsStr.append(key, value);
    });
    
    const queryString = paramsStr.toString();
    if (queryString) {
      endpoint += `?${queryString}`;
    }
    
    console.log(`GET ${endpoint} - Proxying request to backend`);
    
    const response = await fetch(`${backendUrl}${endpoint}`, {
      next: {
        revalidate: 0
      },
      signal: AbortSignal.timeout(600000)
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `Error ${response.status}` }));
      console.error(`GET ${endpoint} - Backend error: ${JSON.stringify(errorData)}`);
      return NextResponse.json(
        { error: errorData.detail || 'Failed to fetch data' },
        { status: response.status }
      );
    }
    
    const data = await response.json();
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error(`GET /api/exam-papers - Error proxying to backend:`, error);
    return NextResponse.json(
      { error: 'Failed to connect to backend service' },
      { status: 500 }
    );
  }
}

export async function POST(request: Request, { params }: { params: { slug: string[] } }) {
  const backendUrl = process.env.NEXT_PUBLIC_GPTR_API_URL || 'http://localhost:8000';
  
  try {
    // Build the endpoint path
    const slugPath = params.slug.join('/');
    let endpoint = '/api/exam-papers';
    if (slugPath) {
      endpoint += `/${slugPath}`;
    }
    
    // Parse the request body
    let body;
    try {
      body = await request.json();
    } catch (parseError) {
      console.error('Error parsing request body:', parseError);
      return NextResponse.json(
        { error: 'Invalid JSON in request body' },
        { status: 400 }
      );
    }
    
    console.log(`POST ${endpoint} - Proxying request to backend`);
    
    const response = await fetch(`${backendUrl}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      next: {
        revalidate: 0
      },
      signal: AbortSignal.timeout(600000)
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `Error ${response.status}` }));
      console.error(`POST ${endpoint} - Backend error: ${JSON.stringify(errorData)}`);
      return NextResponse.json(
        { error: errorData.detail || 'Failed to process request' },
        { status: response.status }
      );
    }
    
    const data = await response.json();
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error(`POST /api/exam-papers - Error proxying to backend:`, error);
    return NextResponse.json(
      { error: 'Failed to connect to backend service' },
      { status: 500 }
    );
  }
}
