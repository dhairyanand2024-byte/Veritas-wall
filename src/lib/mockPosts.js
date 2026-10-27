// lib/mockPosts.js
// Placeholder feed data shaped like what GET /api/posts should return.
// Swap this out for a real fetch once the FastAPI backend is live —
// see the commented-out fetch in App.jsx for where the real call goes.

export const POSTS = [
  {
    id: 'p1',
    dept: 'Computer Science',
    dci: 4.6,
    blindUid: 'a91f-7c3e',
    title: 'My advisor sat on my manuscript for fourteen months and called it mentorship',
    excerpt:
      "The lesson wasn't about the paper. It was that our department has no mechanism for a student to raise a concern about an advisor without that advisor finding out who raised it.",
    body: [
      "I want to be precise about what happened, because the specifics matter more than the feeling.",
      "I submitted a full draft in the spring. Fourteen months later, after three unanswered check-ins, I was told the delay was 'part of learning to be patient as a researcher.' In that time, a collaborator on an adjacent project published something with substantial conceptual overlap.",
      "The structural failure here isn't one advisor being slow. It's that our department's annual review process asks students to self-report advising problems on a form the advisor later co-signs. There is no route that doesn't pass back through the person you're describing.",
      "What I want from this post isn't sympathy — it's for someone building the next version of our grievance process to notice that a form reviewed by both parties isn't a grievance process, it's a negotiation.",
    ],
    timeBucket: 'This week',
    lessons: 12,
    poll: {
      title: 'Should advising complaints route through a third party by default?',
      criteria: [
        { key: 'independence', label: 'Reviewer independence', value: 78 },
        { key: 'speed', label: 'Resolution speed', value: 44 },
        { key: 'disruption', label: 'Disruption to program norms', value: 31 },
      ],
    },
  },
  {
    id: 'p2',
    dept: 'Undergraduate Admin',
    dci: 3.1,
    blindUid: 'e2b0-19af',
    title: 'A financial-aid deadline moved with no notice, and I found out from a hold on my registration',
    excerpt:
      "The deadline itself wasn't the failure. The failure was that the change was announced in a channel nobody in my position was subscribed to.",
    body: [
      "I checked my aid portal weekly. What I didn't check was the general student-life newsletter, which is where the updated deadline was mentioned in paragraph six of an unrelated announcement.",
      "By the time I noticed the hold, late fees had already accrued, and reversing them required a form that itself had a two-week processing window — longer than the time I had left before the next billing cycle.",
      "This is a communication architecture problem: high-stakes financial deadlines and low-stakes campus-life announcements share exactly one channel. Anyone the deadline actually matters to has the least reason to be reading that channel closely.",
    ],
    timeBucket: 'This week',
    lessons: 27,
    poll: {
      title: 'Should high-stakes deadlines require a separate, opt-out-only notification channel?',
      criteria: [
        { key: 'reach', label: 'Guaranteed reach', value: 84 },
        { key: 'noise', label: 'Notification fatigue risk', value: 52 },
        { key: 'cost', label: 'Implementation cost', value: 22 },
      ],
    },
  },
  {
    id: 'p3',
    dept: 'Graduate Research',
    dci: 4.9,
    blindUid: '5d4c-a201',
    title: "Our lab's authorship order was decided in a hallway conversation I wasn't in",
    excerpt:
      "I did the analysis this paper is built on. I found out my place in the author list the same day everyone else did — on the submission confirmation email.",
    body: [
      "There was no meeting. There was no criteria document. Authorship order, in our lab, has always been whatever the PI decides feels right at submission time, and until this project I'd never had a reason to question that.",
      "The specific harm was small — I moved from where I expected to be to one position lower — but the structural issue is that the entire process was invisible until it produced an outcome I could react to but not contest.",
      "What would have prevented this isn't a different outcome necessarily. It's a documented, pre-registered authorship criteria — something several journals already require as a matter of policy but that almost no lab actually implements internally before a dispute forces the question.",
    ],
    timeBucket: 'Last week',
    lessons: 41,
    poll: {
      title: 'Should labs pre-register authorship criteria before a project begins?',
      criteria: [
        { key: 'fairness', label: 'Perceived fairness', value: 88 },
        { key: 'flexibility', label: 'PI flexibility preserved', value: 29 },
        { key: 'overhead', label: 'Administrative overhead', value: 35 },
      ],
    },
  },
];
