import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"

export default function Home() {
  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center px-4">
      <div className="max-w-2xl w-full space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-foreground tracking-tight">
            Attic
          </h1>
          <p className="mt-3 text-lg text-muted-foreground">
            Personal analytics for your TikTok data
          </p>
        </div>

        <Card>
          <CardHeader className="text-center">
            <CardTitle>Welcome to Attic</CardTitle>
            <CardDescription>
              Upload your TikTok data export to get started with personalized
              insights and analytics.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center">
            <Button size="lg">Get Started</Button>
          </CardContent>
        </Card>

        <p className="text-center text-sm text-muted-foreground">
          Alpha preview &middot; More features coming soon
        </p>
      </div>
    </main>
  )
}
